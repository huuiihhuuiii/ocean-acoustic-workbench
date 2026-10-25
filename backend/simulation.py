"""Deterministic parameter drafts and read-only comparisons of actual results.

The parser recognizes explicit quantities only. It neither calls a model nor
invents an environment, missing physical values, or results. Draft != preview
and preview != execution; only the existing jobs endpoint submits a case.
"""
from __future__ import annotations
import itertools
import hashlib
import re
import science

NUMBER=r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?'
SEP=r'\s*(?:[,，、/]|\band\b|和|及)\s*'
DEPTH_UNITS=r'km|cm|mm|千米|公里|厘米|毫米|m|米'
FREQ_UNITS=r'kHz|千赫兹|千赫|Hz|赫兹'
LABELS={
 'range_points':r'距离(?:采样)?(?:点数|网格点)|range\s*(?:points|samples)|range_points',
 'depth_points':r'深度(?:采样)?(?:点数|网格点)|depth\s*(?:points|samples)|depth_points',
 'frequencies_hz':r'频率(?:组合)?|frequenc(?:y|ies)|\bf(?=\s*[:=])',
 'source_depths_m':r'声源(?:深度|位于|放在)|源深(?:度)?|source\s*(?:depths?|at)|source_depths?_m',
 'receiver_depth_m':r'接收(?:器)?(?:深度|位于|放在)|接收深|receiver\s*(?:depth|at)|hydrophone\s*depth|receiver_depth_m',
 'range':r'传播距离|距离(?:范围)?|\brange(?![_a-z])(?:\s*(?:interval|extent))?',
}
DISPLAY={'template':'环境模板','frequencies_hz':'频率','source_depths_m':'声源深度','receiver_depth_m':'接收深度','range_min_km':'起始距离','range_max_km':'终止距离','range_points':'距离点数','depth_points':'深度点数'}
QUESTIONS={'template':'请明确是否使用 Munk 5000 m 理想深海模板；当前不支持真实海域或任意环境。','frequencies_hz':'请给出频率及单位，例如 50 Hz 或 0.05 kHz。','source_depths_m':'请给出声源深度及单位，例如源深 1000 m。','receiver_depth_m':'请给出接收深度及单位，例如接收深度 1000 m。','range_min_km':'请给出起始距离，例如距离 1–50 km。','range_max_km':'请给出终止距离，例如距离 1–50 km。'}
REQUIRED=tuple(QUESTIONS)


def environment_signature(content):
    """Hash the actual ENV, normalizing only declared control-variable lines."""
    lines=[line.strip() for line in content.splitlines() if line.strip()]
    if len(lines)<4:return None
    markers=[index for index,line in enumerate(lines) if re.search(r'!\s*NSD\b',line,re.I)]
    if len(markers)!=1 or markers[0]+1>=len(lines):return None
    if not re.match(r'^1(?:\s|$)',lines[markers[0]]):return None
    lines[1]='<frequency_hz_control>';lines[markers[0]+1]='<source_depth_m_control>'
    return hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest()


def _segments(message):
    alternatives='|'.join(f'(?P<{key}>{value})' for key,value in LABELS.items())
    matches=list(re.finditer(alternatives,message,re.I))
    return [(match.lastgroup,message[match.end():matches[index+1].start() if index+1<len(matches) else len(message)],match.start()) for index,match in enumerate(matches)]


def _quantities(fragment,kind):
    units=FREQ_UNITS if kind=='frequencies_hz' else DEPTH_UNITS
    # Stop at a sentence boundary. A decimal point remains part of a number.
    fragment=re.split(r'[;；。\n]',fragment,maxsplit=1)[0]
    if kind=='range':fragment=re.sub(r'(?<=[\dA-Za-z米])\s*[-–—~～]\s*(?=\d)',' ',fragment)
    found=list(re.finditer(rf'({NUMBER})\s*({units})?',fragment,re.I))
    if not found:return None,'没有识别到明确数值'
    present=[match.group(2) for match in found if match.group(2)]
    if not present:return None,'未给单位，未自动猜测'
    if len(found)>12:return None,'数值过多，请明确列出课程支持的少量控制变量'
    # A final unit may apply to a comma-separated list, but never to a range
    # in frequency/source-depth fields, whose sweep step is unspecified.
    if kind!='range' and len(found)>1 and re.search(r'(?:\d|m|米|Hz|兹)\s*(?:-|–|—|~|～|至|到)\s*\d',fragment,re.I):
        return None,'范围扫描缺少明确步长，请用逗号列出频率或源深'
    values=[]
    for match in found:
        unit=(match.group(2) or present[-1]).lower();value=float(match.group(1))
        scale=1000 if unit in ('khz','千赫','千赫兹','km','千米','公里') else .01 if unit in ('cm','厘米') else .001 if unit in ('mm','毫米') else 1
        values.append(value*scale/(1000 if kind=='range' else 1))
    return values,None


def draft_plan(message):
    if not isinstance(message,str) or not message.strip() or len(message)>12000:
        raise ValueError('请提供 1–12000 字符的仿真问题。')
    plan={};extracted=[];warnings=[];unsupported=[];assumptions=[]
    if re.search(r'(?<![A-Za-z0-9_])munk(?:_5000m)?(?![A-Za-z0-9_])',message,re.I):
        plan['template']='munk_5000m';extracted.append({'field':'template','label':DISPLAY['template'],'raw':'Munk','value':'munk_5000m','unit':None})
    if re.search(r'BELLHOP|\bRAM\b|非相干|incoherent|PE\s*(?:求解|模型)|真实海域|实时海况|浅海|shallow\s*(?:water|sea)|自定义海底|custom\s*(?:bottom|seabed)|南海|东海|黄海|渤海',message,re.I):
        unsupported.append('当前执行器仅支持 Munk/KRAKEN/FIELD 相干简正波；请求中的其他求解器、非相干场或实时真实海域未接入。')
    if re.search(r'(?:执行|运行|修改|删除|安装|execute|run|delete|install).{0,20}(?:命令|代码|脚本|system\(|shell|eval\(|powershell)|os\.system|subprocess|rm\s+-',message,re.I):
        unsupported.append('参数草案不执行代码或命令；仅支持固定课程模板的数值输入。')
    segments=_segments(message)
    if not any(key=='frequencies_hz' for key,_,_ in segments):
        quantity=rf'{NUMBER}\s*(?:{FREQ_UNITS})?'
        for match in re.finditer(rf'{quantity}(?:{SEP}{quantity})*',message,re.I):
            if re.search(FREQ_UNITS,match.group(),re.I):segments.insert(0,('frequencies_hz',match.group(),match.start()))
    seen={}
    for field,fragment,_ in segments:
        if field in ('range_points','depth_points'):
            match=re.match(r'\s*[:=：]?\s*(\d+)\s*(?:点|points?)?',fragment,re.I)
            if not match:continue
            values=int(match.group(1));target={field:values}
        else:
            values,error=_quantities(fragment,field)
            if error:warnings.append(f'{DISPLAY.get(field,"距离")}：{error}。');continue
            if field=='range':
                if len(values)!=2:
                    warnings.append('距离必须明确给出起点与终点，单一距离不自动解释为 0 到该距离。');continue
                target={'range_min_km':values[0],'range_max_km':values[1]}
            elif field=='receiver_depth_m':
                if len(values)!=1:warnings.append('当前仅支持一个接收深度，请明确选择。');continue
                target={field:values[0]}
            else:target={field:sorted(set(values))}
        for key,value in target.items():
            if key in seen and seen[key]!=value:
                plan.pop(key,None);warnings.append(f'{DISPLAY[key]}出现冲突，请明确唯一参数。');seen[key]='conflict';continue
            if seen.get(key)=='conflict':continue
            seen[key]=value;plan[key]=value
            extracted.append({'field':key,'label':DISPLAY[key],'raw':fragment.strip()[:180],'value':value,'unit':'Hz' if key=='frequencies_hz' else 'km' if key.startswith('range_') and key!='range_points' else 'm' if 'depth' in key and key!='depth_points' else 'points'})
    for key,value in [('range_points',201),('depth_points',251)]:
        if key not in plan:
            plan[key]=value;assumptions.append({'field':key,'value':value,'reason':'课程显示采样默认值，可在表单修改；不是求解器收敛结论。'})
    missing=[{'field':key,'label':DISPLAY[key],'question':QUESTIONS[key]} for key in REQUIRED if key not in plan]
    warnings.extend(['Munk 5000 m 理想环境不是指定海域的观测环境。','草案只做显式单位解析；需要参数校验与人工确认后提交，未运行 MATLAB。'])
    return {'parser':'deterministic_units_v1','model_used':False,'draft_plan':plan,'extracted_fields':extracted,'missing_fields':missing,'assumptions':assumptions,'warnings':warnings,'unsupported_requests':unsupported,'validation_errors':[],'ready_for_preview':not missing and not unsupported,'requires_confirmation':True,'execution_started':False}


def compare_cases(cases):
    """2–4 actual result dictionaries; never compute a new solver result."""
    if not 2<=len(cases)<=4:raise ValueError('请选择 2–4 组已完成的不同任务。')
    if len({case['id'] for case in cases})!=len(cases):raise ValueError('比较任务不能重复。')
    series=[]
    for case in cases:
        result,plan=case['result'],case['plan'];validation=science.verify_result(result,plan)
        series.append({'id':case['id'],'plan':plan,'frequency_hz':result.get('frequency_hz'),'source_depth_m':result.get('source_depth_m'),'actual_receiver_depth_m':result.get('actual_receiver_depth_m'),'ranges_m':result.get('ranges_m',[]),'curve_tl_db':result.get('curve_tl_db',[]),'validation':validation,'units':case.get('units',{'range':'m','depth':'m','tl':'dB'}),'evidence':{'result':'result.json','result_sha256':case.get('result_sha256'),'manifest':case.get('manifest')}})
    pairs=[]
    for left,right in itertools.combinations(cases,2):
        report=science.compare_results(left['result'],right['result'],left['plan'],right['plan'])
        # An environment name alone does not establish identical environments.
        # Manifests of new jobs carry hashes; for legacy artifacts compare the
        # ENV structure with only the declared f/source-depth lines normalized.
        same_environment=bool(left.get('environment_signature')) and left.get('environment_signature')==right.get('environment_signature')
        report['checks']['same_environment_input']=same_environment
        report['checks']['same_units']=all(case.get('units',{'range':'m','depth':'m','tl':'dB'})=={'range':'m','depth':'m','tl':'dB'} for case in (left,right))
        report['comparable']=all(report['checks'].values())
        if not report['comparable']:report['deltas']=None
        report['single_factor_controlled']=len(report['changed_controlled_variables'])==1
        report.update(left_id=left['id'],right_id=right['id'])
        pairs.append(report)
    return {'comparable':all(pair['comparable'] for pair in pairs),'pairs':pairs,'series':series,'conditions':['环境输入一致（仅频率、源深可作控制变量）','完整距离/深度轴一致','实际接收深度与 TL 归一化一致','有效样本掩膜一致'],'warnings':['对比不代表数值收敛、真实海域排名或通信性能结论。'],'can_rank_environments':False,'execution_started':False}
