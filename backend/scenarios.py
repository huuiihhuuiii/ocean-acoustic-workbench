"""Expand a validated scene into frozen, independently reproducible cases."""
import custom_environment,classic_environments,hashlib,json

NAMES={'single':'单次计算','source_scan':'声源深度扫描','seasonal':'季节变化对比','bottom_scan':'海底吸收敏感性','model_compare':'同环境模型对比','convergence':'BELLHOP收敛检查'}

def research_cases(plan):
    if len(plan.frequencies_hz)!=1 or len(plan.source_depths_m)!=1:raise ValueError('模型对比与收敛检查每批使用一个频率和一个声源深度')
    if plan.scenario=='convergence':
        if plan.solver!='bellhop' or plan.bellhop_output=='rays':raise ValueError('收敛检查需要BELLHOP传播损失模式')
        if not 1<=plan.beam_count<=10000 or plan.ray_step_m<=0:raise ValueError('收敛检查需显式设置1–10000个波束和大于0的积分步长，不能使用自动值')
    # Validate KRAKEN's trapped-mode assumptions as well as BELLHOP inputs.
    base=plan.model_copy(update={'solver':'kraken' if plan.scenario=='model_compare' else 'bellhop'})
    environment=base.checked() or classic_environments.matched_munk()
    fingerprint=hashlib.sha256(json.dumps({k:environment[k] for k in ['ssp','water_depth_m','water_density_g_cm3','bottom']},sort_keys=True).encode()).hexdigest()
    if plan.scenario=='model_compare':
        variants=[('kraken',{'solver':'kraken'}),('bellhop',{'solver':'bellhop','bellhop_output':plan.mode_addition})]
    else:
        variants=[('baseline',{}),('beams',{'beam_count':plan.beam_count*2}),('step',{'ray_step_m':plan.ray_step_m/2}),('both',{'beam_count':plan.beam_count*2,'ray_step_m':plan.ray_step_m/2})]
    cases=[]
    for role,changes in variants:
        case=plan.model_dump();case.update(changes)
        case['research_base']=plan.model_dump()
        case.update(frequency_hz=plan.frequencies_hz[0],source_depth_m=plan.source_depths_m[0],scenario_name=NAMES[plan.scenario],comparison_role=role,environment_snapshot=environment,water_depth_m=environment['water_depth_m'],environment_fingerprint=fingerprint,ssp_interpolation='C-linear')
        mode=case['mode_addition'] if case['solver']=='kraken' else case['bellhop_output']
        case['case_label']=case['solver'].upper()+' · '+('相干' if mode=='coherent' else '非相干')
        if plan.scenario=='convergence':case['case_label']+=f" · {case['beam_count']}波束 · 步长{case['ray_step_m']:g}m"
        cases.append(case)
    return cases

def expand(plan):
    if plan.scenario not in NAMES:raise ValueError('未知综合场景')
    if plan.solver not in ['kraken','bellhop','scooter']:raise ValueError('未知求解器')
    if plan.solver=='scooter' and plan.scenario in ['model_compare','convergence']:raise ValueError('SCOOTER先使用单次计算、声源或季节扫描；现有模型对比和波束收敛场景适用于KRAKEN/BELLHOP')
    if plan.scenario in ['model_compare','convergence']:return research_cases(plan)
    if plan.scenario=='bottom_scan' and plan.solver!='kraken':raise ValueError('海底吸收扫描使用KRAKEN传播损失；几何声线不能比较吸收损失')
    if plan.scenario in ['seasonal','bottom_scan'] and plan.template!='woa18':raise ValueError('季节与海底扫描需要选择 WOA18 自定义环境')
    if plan.scenario=='source_scan' and len(plan.source_depths_m)<2:raise ValueError('声源扫描至少需要两个源深')
    periods=[13,14,15,16] if plan.scenario=='seasonal' else [plan.period]
    absorptions=plan.bottom_scan_values if plan.scenario=='bottom_scan' else [plan.bottom_attenuation]
    if len(periods)*len(absorptions)*len(plan.frequencies_hz)*len(plan.source_depths_m)>12:raise ValueError('综合场景单批最多12组，请减少频率或源深组合')
    cases=[]
    for period in periods:
        for absorption in absorptions:
            variant=plan.model_copy(update={'period':period,'bottom_attenuation':absorption})
            environment=variant.checked()
            if plan.solver=='scooter':
                if plan.scooter_mesh_points==1:raise ValueError('有限元网格取0自动或至少2个点')
                speeds=[p['sound_speed_m_s'] for p in environment['ssp']]
                cmin=min(speeds)*.9;cmax=max(max(speeds),environment['bottom']['speed_m_s'])*1.1
                nk=2*max(plan.frequencies_hz)*(1/cmin-1/cmax)*plan.range_max_km*plan.scooter_rmax_factor*1000+2
                if nk*(plan.depth_points+plan.range_points)>20000000:raise ValueError('SCOOTER谱积分矩阵过大，请减少距离、RMAX倍数或接收网格点数')
            for f in plan.frequencies_hz:
                for z in plan.source_depths_m:
                    case=variant.model_dump();
                    if plan.solver=='scooter':case['mode_addition']='coherent'
                    case.update(frequency_hz=f,source_depth_m=z,scenario_name=NAMES[plan.scenario])
                    case['case_label']=f'{plan.solver.upper()} · {f:g} Hz · 源深 {z:g} m'+(' · '+['1—3月','4—6月','7—9月','10—12月'][period-13] if plan.scenario=='seasonal' else f' · 吸收 {absorption:g} dB/波长' if plan.scenario=='bottom_scan' else '')
                    output=plan.bellhop_output if plan.solver=='bellhop' else 'coherent' if plan.solver=='scooter' else plan.mode_addition
                    case['case_label'] += ' · '+{'rays':'声线','coherent':'相干','incoherent':'非相干'}[output]
                    if environment:case['environment_snapshot']=environment
                    cases.append(case)
    return cases
