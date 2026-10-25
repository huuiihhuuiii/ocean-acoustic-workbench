"""Original simulation physics and visualization; the v0.7 durable queue owns execution."""
import json,math,time,statistics,uuid,hashlib,shutil,re
from pathlib import Path
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,Field,field_validator,ConfigDict
import custom_environment,classic_environments,scenarios,solver_results,field_plots,comparison,persistence,ocean_data,task_files
stamp=persistence.now

class Plan(BaseModel):
    model_config=ConfigDict(extra="forbid")
    solver:str='kraken'
    scooter_rmax_factor:float=Field(default=2,ge=1,le=8)
    scooter_mesh_points:int=Field(default=0,ge=0,le=20000)
    mode_addition:str='incoherent'
    bellhop_output:str='rays'
    beam_count:int=Field(default=0,ge=0,le=20000)
    convergence_tolerance_db:float=Field(default=1.0,ge=.01,le=20)
    scenario:str='single'
    bottom_scan_values:list[float]=Field(default=[0,0.8,1.6],min_length=2,max_length=4)
    ray_count:int=Field(default=51,ge=11,le=201)
    angle_min_deg:float=Field(default=-20,ge=-89,le=89)
    angle_max_deg:float=Field(default=20,ge=-89,le=89)
    ray_step_m:float=Field(default=0,ge=0,le=100)
    frequencies_hz:list[float]=Field(default=[50],min_length=1,max_length=4)
    source_depths_m:list[float]=Field(default=[1000],min_length=1,max_length=3)
    receiver_depth_m:float=Field(default=1000,gt=0,lt=5500)
    range_min_km:float=Field(default=1,ge=0.1,le=99)
    range_max_km:float=Field(default=50,gt=0.1,le=100)
    range_points:int=Field(default=201,ge=51,le=501)
    depth_points:int=Field(default=251,ge=51,le=501)
    template:str='munk_5000m'
    longitude:float=Field(default=120,ge=-180,le=180)
    latitude:float=Field(default=20,ge=-90,le=90)
    period:int=Field(default=0,ge=0,le=16)
    water_depth_m:float=Field(default=3500,ge=50,le=5500)
    bottom_speed_m_s:float=Field(default=1600,ge=1400,le=3000)
    bottom_density_g_cm3:float=Field(default=1.8,ge=1,le=3)
    bottom_attenuation:float=Field(default=0.8,ge=0,le=2)
    @field_validator('frequencies_hz')
    @classmethod
    def freqs(cls,v):
        if any(not math.isfinite(f) or f<10 or f>200 for f in v):raise ValueError('首版频率范围 10–200 Hz')
        return sorted(set(v))
    @field_validator('source_depths_m')
    @classmethod
    def depths(cls,v):
        if any(not math.isfinite(f) or f<=0 or f>=5500 for f in v):raise ValueError('源深须在 0–5500 m 内，并小于环境水深')
        return sorted(set(v))
    def checked(self):
        if self.solver not in ['kraken','bellhop','scooter']:raise HTTPException(422,'未知求解器')
        if self.mode_addition not in ['coherent','incoherent']:raise HTTPException(422,'未知模态叠加方式')
        if self.bellhop_output not in ['rays','coherent','incoherent']:raise HTTPException(422,'未知BELLHOP输出模式')
        if self.angle_max_deg<=self.angle_min_deg:raise HTTPException(422,'发射角上限须大于下限')
        if any(not math.isfinite(v) or not 0<=v<=2 for v in self.bottom_scan_values):raise HTTPException(422,'海底吸收扫描范围0–2 dB/波长')
        if self.range_max_km<=self.range_min_km:raise HTTPException(422,'最大距离须大于最小距离')
        if self.template not in ['munk_5000m','woa18','pekeris_100m','constant_5000m']:raise HTTPException(422,'未知环境类型')
        if len(self.frequencies_hz)*len(self.source_depths_m)>12:raise HTTPException(422,'单批最多12组')
        if self.template in ['pekeris_100m','constant_5000m']:
            try:return classic_environments.prepare(self)
            except ValueError as e:raise HTTPException(422,str(e))
        if self.template=='woa18':
            try:return custom_environment.prepare(self)
            except (ValueError,FileNotFoundError) as e:raise HTTPException(422,str(e))
        if max(self.source_depths_m)>=5000 or self.receiver_depth_m>=5000:raise HTTPException(422,'Munk 模板源深与接收深度须小于5000 m')
        return classic_environments.matched_munk() if self.solver=='scooter' else None

def plot_result(folder):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    data=json.loads((folder/'result.json').read_text(encoding='utf-8-sig'))
    solver_results.field_metadata(folder,data)
    (folder/'result.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    solver_results.extra_plots(folder,data)
    if data.get('solver')=='bellhop' and 'tl_db' not in data:
        data['created']=stamp()
        (folder/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return
    x=np.asarray(data['ranges_m'])/1000;z=np.asarray(data['depths_m']);tl=np.asarray(data['tl_db'],dtype=float)
    if tl.shape!=(len(z),len(x)) or not np.isfinite(tl).any():raise ValueError('结果维度或有效值校验失败')
    field_plots.render(folder,data)
    data['tl_min_db']=float(np.nanmin(tl));data['tl_max_db']=float(np.nanmax(tl));data['tl_median_db']=float(np.nanmedian(tl));data['created']=stamp()
    (folder/'summary.json').write_text(json.dumps({k:v for k,v in data.items() if k not in ['tl_db','ranges_m','depths_m','curve_tl_db']},ensure_ascii=False,indent=2),encoding='utf-8')

def preview(plan:Plan):
    try:cases=scenarios.expand(plan)
    except ValueError as e:raise HTTPException(422,str(e))
    environment=cases[0].get('environment_snapshot')
    warnings=(environment['assumptions'] if environment else ['Munk 5000 m 示例环境，不代表指定真实海域'])
    if environment and 'profile' in environment:warnings=warnings+[f"实际温盐格点 {environment['profile']['selected']['lon']:g}° / {environment['profile']['selected']['lat']:g}°；每组环境在提交时独立保存。"]
    warnings += ([('BELLHOP 声线路径，不计算传播损失。' if plan.bellhop_output=='rays' else 'BELLHOP '+('相干' if plan.bellhop_output=='coherent' else '非相干')+'声场；采用几何波束，高频近似，低频结果需谨慎解释。请增加波束数量、减半积分步长检查收敛。')] if plan.solver=='bellhop' else [('相干' if plan.mode_addition=='coherent' else '非相干')+'模态叠加；接收深度采用最近网格点。'])
    if plan.solver=='scooter':warnings=[w for w in warnings if '模态叠加' not in w]+['SCOOTER 谱积分相干声场；C线性剖面，RP正波数圆柱远场变换；积分RMAX取最大接收距离的倍数，增大倍数或细化有限元网格检查稳定性。']
    if plan.scenario=='model_compare':warnings+=['两种模型共用环境快照、C线性插值和叠加方式；BELLHOP受高频近似及发射角覆盖影响，差异不能直接当作计算错误。']
    if plan.scenario=='convergence':warnings+=['分别调整波束数和步长，检查4对结果的曲线、全网格及有效点覆盖；局部稳定性不能证明物理精度。']
    return {'environment':environment,'plan':plan.model_dump(),'case_count':len(cases),'warnings':warnings,'cases':[{'frequency_hz':c['frequency_hz'],'source_depth_m':c['source_depth_m'],'label':c['case_label']} for c in cases]}


def required(plan):
    return ['bellhop.exe'] if plan.get('solver')=='bellhop' else ['scooter.exe'] if plan.get('solver')=='scooter' else ['kraken.exe','field.exe']


def prepare_case(folder,plan,cfg,root):
    case={**plan,'toolbox_path':cfg['toolbox_path'],'template_env':str(Path(cfg['toolbox_path'])/'tests/Munk/MunkK.env')}
    environment=plan.get('environment_snapshot')
    if environment:
        (folder/'case.env').write_text(custom_environment.env_text(environment,plan['frequency_hz'],plan['source_depth_m'],plan['depth_points']),encoding='ascii')
        (folder/'environment.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'ssp.csv').write_text('depth_m,sound_speed_m_s\n'+'\n'.join(f"{p['depth_m']},{p['sound_speed_m_s']}" for p in environment['ssp'])+'\n',encoding='utf-8')
        case['water_depth_m']=environment['water_depth_m']
    (folder/'case.json').write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(Path(root)/'backend/matlab/run_studio_case.m',folder/'run_studio_case.m')


def submit(plan,store,wake,scope='studio',key=None):
    try:
        cases=[{**case,'studio':True} for case in scenarios.expand(plan)]
        result=store.submit(plan.model_dump(),scope=scope,idempotency_key=key,cases=cases)
    except persistence.StoreError as exc:raise HTTPException(exc.status,str(exc)) from None
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    wake.set();return result


def batch_results(identity,store,local):
    if not re.fullmatch(r'[a-f0-9]{12}(?:[a-f0-9]{20})?',identity):raise HTTPException(400,'非法批次')
    with store.connection() as db:rows=db.execute('SELECT * FROM jobs WHERE batch_id=? ORDER BY rowid',(identity,)).fetchall()
    items=[];plans=[];results={}
    for row in rows:
        plan=json.loads(row['plan']);plans.append({**plan,'_job_id':row['id']})
        item={'id':row['id'],'state':row['state'],'label':plan.get('case_label',row['id']),'solver':plan.get('solver','kraken'),'comparison_role':plan.get('comparison_role')}
        folder=Path(local)/'runs'/row['id']
        if row['state']=='SUCCEEDED':
            data=json.loads((folder/'result.json').read_text(encoding='utf-8-sig'));summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
            results[row['id']]=data;item['summary']={k:v for k,v in summary.items() if k!='environment'}
            if 'curve_tl_db' in data:
                item.update(ranges_m=data['ranges_m'],curve_tl_db=data['curve_tl_db'])
                values=[v for v in data['curve_tl_db'] if v is not None and math.isfinite(v)]
                item['receiver_curve_median_db']=float(statistics.median(values)) if values else None
        items.append(item)
    if not items:raise HTTPException(404,'批次不存在')
    return {'id':identity,'cases':items,'complete':all(c['state'] not in ['QUEUED','RUNNING'] for c in items),'analysis':comparison.analyze(plans,results)}


def router(store,local,wake):
    api=APIRouter()
    @api.post('/api/simulation/plans/preview')
    def check(plan:Plan):return preview(plan)
    @api.post('/api/simulation/jobs')
    def create(plan:Plan,request:Request):return submit(plan,store,wake,'studio:'+request.headers.get('x-ocean-submission-scope','local'),request.headers.get('idempotency-key'))
    @api.get('/api/batches/{identity}')
    def batch(identity:str):return batch_results(identity,store,local)
    @api.get('/api/ocean-data')
    def catalog():return ocean_data.catalog()
    @api.get('/api/ocean-data/profile')
    def profile(lon:float=120,lat:float=20,period:int=0):
        try:return ocean_data.profile(lon,lat,period)
        except (ValueError,FileNotFoundError) as exc:raise HTTPException(422,str(exc)) from None
    @api.get('/api/ocean-data/terrain')
    def terrain(west:float=95,east:float=145,south:float=-5,north:float=45):
        try:return ocean_data.terrain_map(west,east,south,north)
        except (ValueError,FileNotFoundError) as exc:raise HTTPException(422,str(exc)) from None
    @api.get('/api/validation/{kind}')
    def validation(kind:str):
        if kind not in ('studio','scooter','migration'):raise HTTPException(404)
        path=Path(local)/(kind+'-validation.json')
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'passed':False,'records':[]}
    return api
