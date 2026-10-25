from __future__ import annotations
import os, sys, json, sqlite3, threading, subprocess, queue, uuid, time, shutil, io, zipfile, re, math, hashlib
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationError
from typing import Literal
import httpx
import knowledge, models, science, answer_policy, context_budget, public_ocean, persistence, simulation
import research_api, project_browser, simulation_studio, task_files

ROOT=Path(__file__).resolve().parents[1]; LOCAL=Path(os.environ.get('OCEAN_RUNTIME_DIR',str(ROOT/'.local')))
DB=LOCAL/'workbench.sqlite3'; CONFIG=LOCAL/'config.json'
STORE=persistence.JobStore(DB)
def connect():return STORE.connection()
def config():return json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}
def stamp():return datetime.now().astimezone().isoformat(timespec='seconds')
def kbfile(name):return LOCAL/'kb'/name
def claims():return knowledge.knowledge_cards()
def sources():return json.loads(kbfile('source_registry.json').read_text(encoding='utf-8'))['sources']
def job(id):
    value=STORE.get(id) or RESEARCH.get(id)
    if not value:raise HTTPException(404,'任务不存在')
    return value
def run_dir(id):
    if not re.fullmatch(r'[a-f0-9]{12}',id):raise HTTPException(400,'非法任务标识')
    return LOCAL/'runs'/id
PROCESSES={};PAUSED=False;STATELOCK=threading.RLock();PDFLOCK=threading.Lock()
CANCEL_REQUESTS=set();WORKER_ERROR=None
WORKER_STOP=threading.Event();WORKER_WAKE=threading.Event();WORKER_ACTIVE=False;WORKER_THREAD=None
WORKER_LOCK=persistence.WorkerLock(DB.with_suffix('.worker.lock'));WORKER_OWNER=uuid.uuid4().hex

class Plan(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    frequencies_hz:list[float]=Field(default=[50],min_length=1,max_length=4)
    source_depths_m:list[float]=Field(default=[1000],min_length=1,max_length=3)
    receiver_depth_m:float=Field(default=1000,gt=0,lt=5000)
    range_min_km:float=Field(default=1,ge=0.1,le=99)
    range_max_km:float=Field(default=50,gt=0.1,le=100)
    range_points:int=Field(default=201,ge=51,le=501)
    depth_points:int=Field(default=251,ge=51,le=501)
    template:str='munk_5000m'
    @field_validator('frequencies_hz')
    @classmethod
    def freqs(cls,v):
        if any(not math.isfinite(f) or f<10 or f>200 for f in v):raise ValueError('首版频率范围 10–200 Hz')
        return sorted(set(v))
    @field_validator('source_depths_m')
    @classmethod
    def depths(cls,v):
        if any(not math.isfinite(f) or f<=0 or f>=5000 for f in v):raise ValueError('源深须在 0–5000 m 内')
        return sorted(set(v))
    def checked(self):
        if self.range_max_km<=self.range_min_km:raise HTTPException(422,'最大距离须大于最小距离')
        if self.template!='munk_5000m':raise HTTPException(422,'首版仅支持已接入的 Munk 模板')
        if len(self.frequencies_hz)*len(self.source_depths_m)>12:raise HTTPException(422,'单批最多12组')

def plot_result(folder,plan):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    data=json.loads((folder/'result.json').read_text(encoding='utf-8-sig'))
    validation=science.validate_result(data,plan)
    analysis=science.analyze_result(data,plan)
    x=np.asarray(data['ranges_m'])/1000;z=np.asarray(data['depths_m']);tl=np.asarray(data['tl_db'],dtype=float)
    if tl.shape!=(len(z),len(x)) or not np.isfinite(tl).any():raise ValueError('结果维度或有效值校验失败')
    fig,ax=plt.subplots(figsize=(10,5),facecolor='#f6fafb');fig.subplots_adjust(left=.09,right=.95,bottom=.14,top=.9)
    im=ax.pcolormesh(x,z,tl,shading='auto',cmap='viridis_r',vmin=40,vmax=110);ax.invert_yaxis();ax.set(xlabel='Range (km)',ylabel='Depth (m)',title=f"KRAKEN · {data['frequency_hz']:g} Hz · source {data['source_depth_m']:g} m")
    fig.colorbar(im,ax=ax,label='TL (dB)');fig.savefig(folder/'tl_map.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,3.5),facecolor='#f6fafb');ax.plot(x,data['curve_tl_db'],color='#07828c',lw=1.2);ax.set(xlabel='Range (km)',ylabel='TL (dB)',title=f"Receiver depth {data['actual_receiver_depth_m']:g} m");ax.grid(alpha=.16);fig.tight_layout();fig.savefig(folder/'tl_curve.png',dpi=150);plt.close(fig)
    data['tl_min_db']=float(np.nanmin(tl));data['tl_max_db']=float(np.nanmax(tl));data['tl_median_db']=float(np.nanmedian(tl));data['created']=stamp()
    data['validation']=validation;data['analysis']=analysis
    (folder/'summary.json').write_text(json.dumps({k:v for k,v in data.items() if k not in ['tl_db','ranges_m','depths_m','curve_tl_db']},ensure_ascii=False,indent=2),encoding='utf-8')
    science.write_manifest(folder.name,plan,folder,validation,analysis,finished_at=data['created'])

def worker():
    global WORKER_ACTIVE,PAUSED,WORKER_ERROR
    while not WORKER_STOP.is_set():
        if not WORKER_LOCK.acquire():
            WORKER_STOP.wait(2);continue
        try:
            STORE.recover_running();WORKER_ACTIVE=True;WORKER_ERROR=None
            while not WORKER_STOP.is_set():
                PAUSED=STORE.paused()
                case_job=STORE.claim_next(WORKER_OWNER)
                if not case_job:
                    WORKER_WAKE.wait(.75);WORKER_WAKE.clear();continue
                execute_job(case_job)
        except (sqlite3.Error,OSError) as error:
            WORKER_ERROR='持久队列暂不可用，任务已保留；请检查数据库及运行目录。'
            print('Queue unavailable:',type(error).__name__,flush=True);WORKER_STOP.wait(2)
        finally:
            WORKER_ACTIVE=False;WORKER_LOCK.release()

def execute_job(case_job):
    id=case_job['id'];plan=case_job['plan']
    try:
        if WORKER_STOP.is_set():
            STORE.finish(id,'INTERRUPTED','服务停止，任务未启动；请核对后重新提交。',owner=WORKER_OWNER);return
        cfg=config();folder=run_dir(id);folder.mkdir(parents=True,exist_ok=True)
        executable=Path(cfg.get('matlab_path',''))
        if not executable.is_file():raise RuntimeError('MATLAB 路径不存在，请检查环境配置')
        toolbox=Path(cfg['toolbox_path'])
        for name in (simulation_studio.required(plan) if plan.get('studio') else ['kraken.exe','field.exe']):
            if not (toolbox/'bin'/name).is_file():raise RuntimeError('缺少 '+name)
        runner='run_studio_case' if plan.get('studio') else 'run_ocean_case'
        if plan.get('studio'):simulation_studio.prepare_case(folder,plan,cfg,ROOT)
        else:
            case={**plan,'toolbox_path':str(toolbox),'template_env':str(toolbox/'tests/Munk/MunkK.env')}
            (folder/'case.json').write_text(json.dumps(case,ensure_ascii=False),encoding='utf-8')
            shutil.copy2(ROOT/'backend/matlab/run_ocean_case.m',folder/'run_ocean_case.m')
        solver_start=time.monotonic()
        with (folder/'run.log').open('wb') as log:
            log.write(('任务 '+id+'\n'+('MATLAB KRAKEN / SCOOTER / BELLHOP；冻结环境见 case.json' if plan.get('studio') else 'MATLAB 固定 Munk 模板')+'\n以下保留实际进程输出\n').encode());log.flush()
            with STATELOCK:
                if job(id)['state']!='RUNNING':return
                if WORKER_STOP.is_set():
                    STORE.finish(id,'INTERRUPTED','服务停止，任务未启动。',owner=WORKER_OWNER);return
                proc=subprocess.Popen([str(executable),'-wait','-noFigureWindows','-batch',runner],cwd=folder,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
                PROCESSES[id]=proc
            try:code=proc.wait(timeout=int(cfg.get('timeout_seconds',240)))
            except subprocess.TimeoutExpired:
                if not kill(id):
                    STORE.set_paused(True);raise RuntimeError('计算超时且未确认进程停止，队列已暂停，请管理员检查残留进程。')
                raise RuntimeError('计算超时，当前任务已终止')
        while id in CANCEL_REQUESTS and not WORKER_STOP.is_set():time.sleep(.02)
        if job(id)['state']!='RUNNING':return
        if WORKER_STOP.is_set():
            STORE.finish(id,'INTERRUPTED','服务停止导致计算中断；未自动重跑。',owner=WORKER_OWNER);return
        if code!=0:raise RuntimeError('MATLAB 运行失败，退出码 '+str(code)+'；请查看日志')
        if not (folder/'result.json').exists():raise RuntimeError('缺少本次 result.json')
        if plan.get('studio'):
            data=json.loads((folder/'result.json').read_text(encoding='utf-8-sig'));data['solver_elapsed_seconds']=round(time.monotonic()-solver_start,3)
            (folder/'result.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            simulation_studio.plot_result(folder)
        else:plot_result(folder,plan)
        STORE.finish(id,'SUCCEEDED',owner=WORKER_OWNER)
    except Exception as exc:
        STORE.finish(id,'INTERRUPTED' if WORKER_STOP.is_set() else 'FAILED',str(exc)[:1000],owner=WORKER_OWNER)
    finally:PROCESSES.pop(id,None)
def kill(id):
    proc=PROCESSES.get(id)
    if not proc or proc.poll() is not None:return True
    try:
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
        else:
            import signal
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name!='nt':
                os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
    except (OSError,subprocess.TimeoutExpired):pass
    return proc.poll() is not None
@asynccontextmanager
async def app_lifespan(application):
    start_executor()
    RESEARCH.migrate()
    try:
        refresh_public_ocean_startup()
        yield
    finally:
        await RESEARCH.close()
        stop_executor()

app=FastAPI(title='海洋声学工作台',docs_url='/api/docs',lifespan=app_lifespan)
RESEARCH=research_api.ResearchService(ROOT,LOCAL,STORE,config,lambda query:knowledge.retrieve(query))
app.include_router(research_api.router(RESEARCH))
app.include_router(simulation_studio.router(STORE,LOCAL,WORKER_WAKE))
RESEARCH.fixed_schema=lambda:{'schema':simulation_studio.Plan.model_json_schema(),'solvers':['kraken','scooter','bellhop'],'templates':['munk_5000m','pekeris_100m','woa18','constant_5000m']}
RESEARCH.fixed_preview=lambda plan:simulation_studio.preview(simulation_studio.Plan(**plan))
RESEARCH.fixed_submit=lambda plan:simulation_studio.submit(simulation_studio.Plan(**plan),STORE,WORKER_WAKE)
RESEARCH.fixed_details=lambda identity:details(identity)
RESEARCH.fixed_batch=lambda identity:simulation_studio.batch_results(identity,STORE,LOCAL)

def start_executor():
    global WORKER_THREAD,PAUSED
    STORE.migrate();PAUSED=STORE.paused();WORKER_STOP.clear()
    if os.environ.get('OCEAN_DISABLE_WORKER')!='1':
        WORKER_THREAD=threading.Thread(target=worker,daemon=True);WORKER_THREAD.start()

def stop_executor():
    WORKER_STOP.set();WORKER_WAKE.set()
    with STATELOCK:
        for id in list(PROCESSES):
            if not kill(id):STORE.set_paused(True)
    if WORKER_THREAD:WORKER_THREAD.join(timeout=10)

def refresh_public_ocean_startup():
    if os.environ.get('OCEAN_DISABLE_PUBLIC_REFRESH')!='1':public_ocean.refresh_if_stale(ttl_hours=168,background=True)

@app.middleware('http')
async def local_guard(request:Request,call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ['127.0.0.1','localhost','testserver']:return Response('Local service only',status_code=403)
    origin=request.headers.get('origin')
    if request.method not in ['GET','HEAD','OPTIONS'] and origin and origin not in ['http://127.0.0.1:8765','http://localhost:8765','http://127.0.0.1:5173','http://localhost:5173']:return Response('Invalid origin',status_code=403)
    return await call_next(request)

@app.get('/api/health')
def health():
    cfg=config();t=Path(cfg.get('toolbox_path','.'))
    return {'version':'0.7.0','matlab_available':Path(cfg.get('matlab_path','')).is_file(),'matlab_version':'R2024a','solver_available':(t/'bin/kraken.exe').is_file() and (t/'bin/field.exe').is_file(),'model_configured':bool(cfg.get('api_key')),'knowledge_cards':len(claims()),'model_name':next((m['name'] for m in models.catalog()['models'] if m['provider']==cfg.get('provider') and m['id']==cfg.get('model')),cfg.get('model','')),'provider_name':next((p['name'] for p in models.catalog()['providers'] if p['id']==cfg.get('provider')),cfg.get('provider','')),'sources':len(sources()),'paused':PAUSED}
@app.get('/api/config')
def get_config():
    cfg=config();cfg['api_key_set']=bool(cfg.pop('api_key',''));cfg.update(public_mode=False,storage='local_private');return cfg
@app.post('/api/session/clear-keys')
def clear_model_keys():
    cfg=config();cfg['api_key']='';CONFIG.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    saved=models.profiles(config)
    for entry in saved.values():entry['api_key']=''
    (LOCAL/'model-profiles.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'cleared':True,**get_config()}
@app.put('/api/config')
async def save_config(request:Request):
    data=await request.json();cfg=config()
    old_provider=cfg.get('provider');new_provider=data.get('provider',old_provider)
    if new_provider not in [p['id'] for p in models.catalog()['providers']]:raise HTTPException(422,'未知供应商')
    if new_provider!=old_provider:
        models.store_profile(cfg)
        cfg['api_key']=models.profiles(config).get(new_provider,{}).get('api_key','')
    allowed=['matlab_path','toolbox_path','project_path','provider','base_url','model','api_key','timeout_seconds']
    for key in allowed:
        if key in data and (key!='api_key' or data[key]):cfg[key]=data[key]
    if data.get('clear_api_key'):cfg.pop('api_key',None)
    models.validate_endpoint(cfg['provider'],str(cfg.get('base_url','')))
    if not 30<=int(cfg.get('timeout_seconds',240))<=600:raise HTTPException(422,'超时范围30–600秒')
    models.store_profile(cfg)
    CONFIG.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8');return {'saved':True,**get_config()}
@app.post('/api/environment/check')
def check_environment():
    cfg=config();tool=Path(cfg.get('toolbox_path','.'));prj=Path(cfg.get('project_path','.'))
    return {'checks':[{'name':'MATLAB 可执行程序','ok':Path(cfg.get('matlab_path','')).is_file(),'detail':cfg.get('matlab_path','')},{'name':'KRAKEN / FIELD 求解器','ok':all((tool/'bin'/x).is_file() for x in ['kraken.exe','field.exe']),'detail':str(tool/'bin')},{'name':'Munk 成对输入','ok':all((tool/'tests/Munk'/x).is_file() for x in ['MunkK.env','MunkK.flp']),'detail':'5000 m 深海；50 Hz 原始示例'},{'name':'授权项目目录','ok':prj.is_dir(),'detail':str(prj)},{'name':'模型 API Key','ok':bool(cfg.get('api_key')),'detail':'已保存' if cfg.get('api_key') else '未配置；图谱浏览与模板仿真仍可用'}]}
@app.get('/api/graph')
def graph():return knowledge.graph_data()
@app.get('/api/graph/path')
def graph_path(source:str,target:str):
    try:return knowledge.shortest_path(source,target)
    except ValueError as e:raise HTTPException(422,str(e))
@app.get('/api/models/catalog')
def model_catalog():return models.catalog()
@app.get('/api/models/profiles')
def model_profiles():return models.public_profiles(config)
@app.post('/api/models/test')
async def model_test(request:Request):return await models.test_connection(await request.json(),config)
@app.post('/api/models/list')
async def account_models(request:Request):return await models.list_account_models(await request.json(),config)
@app.get('/api/sources')
def list_sources():
    coverage={row['source_id']:row for row in knowledge.retrieval_status().get('source_coverage',[])}
    return [{**s,'available':(LOCAL/'sources'/(s['id']+'.pdf')).exists(),'index_status':f"已索引 {coverage[s['id']]['indexed_pages']} 页" if s['id'] in coverage else '尚未正文入库','coverage':coverage.get(s['id'])} for s in sources()]
@app.get('/api/source/{source_id}')
def source_file(source_id:str):
    if source_id not in [s['id'] for s in sources()]:raise HTTPException(404)
    path=LOCAL/'sources'/(source_id+'.pdf')
    if not path.exists():raise HTTPException(404,'此来源尚未提供在线预览')
    return FileResponse(path,media_type='application/pdf')
@app.get('/api/source/{source_id}/page/{page}')
def source_image(source_id:str,page:int):
    if source_id not in [s['id'] for s in sources()]:raise HTTPException(404)
    path=LOCAL/'sources'/(source_id+'.pdf');cache=LOCAL/'page-images'/f'{source_id}-{page}.png'
    if not path.is_file():raise HTTPException(404)
    # PDFium is not thread-safe. A drawer requests several pages simultaneously.
    with PDFLOCK:
        if not cache.exists():
            import pypdfium2 as pdfium
            with pdfium.PdfDocument(str(path)) as pdf:
                if page<1 or page>len(pdf):raise HTTPException(404)
                cache.parent.mkdir(exist_ok=True);p=pdf[page-1];bitmap=p.render(scale=1.25)
                try:bitmap.to_pil().save(cache)
                finally:bitmap.close();p.close()
    return FileResponse(cache,media_type='image/png')
@app.get('/api/knowledge/code')
def knowledge_code(node:str,reference:int):
    item=next((n for n in knowledge.graph_data()['nodes'] if n['id']==node and n['kind']=='knowledge'),None)
    if not item or reference<0 or reference>=len(item['references']):raise HTTPException(404,'未登记的知识来源')
    ref=item['references'][reference];locator=ref.get('locator','').split(':')[0]
    if ref.get('pdf_page'):raise HTTPException(422,'此来源为 PDF')
    if locator.startswith('at/'):
        base=Path(config()['toolbox_path']).resolve();path=(base/locator[3:]).resolve()
    elif locator.startswith('backend/'):
        base=(ROOT/'backend').resolve();path=(ROOT/locator).resolve()
    else:raise HTTPException(404,'此来源尚未提供代码预览')
    if not path.is_relative_to(base) or not path.is_file() or path.suffix.lower() not in ['.m','.env','.flp','.py']:raise HTTPException(404,'源文件不可预览')
    content=path.read_text(encoding='utf-8',errors='replace')
    return Response(content='来源：'+ref['locator']+'\n\n'+content,media_type='text/plain; charset=utf-8')
@app.get('/api/knowledge/search')
def search(q:str=''):return knowledge.retrieve(q)
@app.get('/api/knowledge/status')
def knowledge_status():
    public_ocean.refresh_if_stale(ttl_hours=168,background=True)
    return knowledge.retrieval_status()
@app.get('/api/knowledge/public-sources')
def public_sources():return public_ocean.public_ocean_status()['web_sources']
@app.get('/api/exercises')
def exercises():return json.loads((ROOT/'backend/data/exercises.json').read_text(encoding='utf-8'))
class DraftRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    message:str=Field(min_length=1,max_length=12000)

@app.post('/api/plans/draft')
def plan_draft(body:DraftRequest):
    result=simulation.draft_plan(body.message)
    try:
        candidate=Plan(**result['draft_plan'])
        if not result['missing_fields']:candidate.checked()
    except ValidationError as error:
        result['validation_errors']=[{'field':'.'.join(map(str,item['loc'])),'message':item['msg']} for item in error.errors()]
    except HTTPException as error:result['validation_errors']=[{'field':'plan','message':error.detail}]
    result['ready_for_preview']=bool(result['ready_for_preview'] and not result['validation_errors'])
    result['case_count']=len(result['draft_plan'].get('frequencies_hz',[]))*len(result['draft_plan'].get('source_depths_m',[])) or None
    return result

@app.post('/api/plans/preview')
def preview(plan:Plan):
    plan.checked();return {'plan':plan.model_dump(),'case_count':len(plan.frequencies_hz)*len(plan.source_depths_m),'warnings':['Munk 5000 m 示例环境，不代表指定真实海域','接收深度使用最近网格点，结果显示实际深度','相干简正波计算；固定 TL 色标 40–110 dB'],'cases':[{'frequency_hz':f,'source_depth_m':z} for f in plan.frequencies_hz for z in plan.source_depths_m]}
@app.post('/api/jobs')
def submit(plan:Plan,request:Request):
    plan.checked()
    try:result=STORE.submit(plan.model_dump(),scope=request.headers.get('x-ocean-submission-scope','local'),idempotency_key=request.headers.get('idempotency-key'))
    except persistence.StoreError as error:raise HTTPException(error.status,str(error)) from None
    WORKER_WAKE.set();return result

class ComparisonRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    ids:list[str]=Field(min_length=2,max_length=4)
    @field_validator('ids')
    @classmethod
    def valid_ids(cls,values):
        if len(set(values))!=len(values) or any(not re.fullmatch(r'[a-f0-9]{12}',value) for value in values):raise ValueError('请选择 2–4 个不同的有效作业标识。')
        return values

@app.post('/api/jobs/compare')
def compare_jobs(body:ComparisonRequest):
    cases=[]
    for id in body.ids:
        value=job(id)
        if value['state']!='SUCCEEDED':raise HTTPException(409,'只能比较已经完成且通过验证的任务。')
        folder=run_dir(id);result_path=folder/'result.json';env_path=folder/'case.env';manifest_path=folder/'manifest.json'
        if not result_path.is_file():raise HTTPException(409,'已有任务缺少实际 result.json，不能对比。')
        try:result=json.loads(result_path.read_text(encoding='utf-8-sig'))
        except (ValueError,OSError):raise HTTPException(409,'已有结果文件不可读取，不能对比。') from None
        if not isinstance(result,dict) or not science.verify_result(result,value['plan'])['ok']:raise HTTPException(409,'已有结果未通过数值一致性校验，不能对比。')
        manifest=None
        if manifest_path.is_file():
            try:
                data=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
                if data.get('job_id')!=id:raise ValueError('job mismatch')
                recorded={item['name']:item['sha256'] for item in data.get('artifacts',[])}
                for name,path in [('result.json',result_path),('case.env',env_path)]:
                    if name in recorded and (not path.is_file() or science.file_sha256(path)!=recorded[name]):raise ValueError('artifact mismatch')
                manifest={'artifact':'manifest.json','sha256':science.file_sha256(manifest_path),'result_hash_verified':'result.json' in recorded,'environment_hash_verified':'case.env' in recorded}
            except (ValueError,OSError,KeyError,TypeError):raise HTTPException(409,'已有产物与溯源记录不一致，不能对比。') from None
        try:environment=simulation.environment_signature(env_path.read_text(encoding='utf-8-sig')) if env_path.is_file() else None
        except (OSError,UnicodeError):raise HTTPException(409,'已有环境文件不可读取，不能核验对比条件。') from None
        cases.append({'id':id,'plan':value['plan'],'result':result,'result_sha256':science.file_sha256(result_path),'manifest':manifest,'units':result.get('units',{'range':'m','depth':'m','tl':'dB'}),'environment_signature':environment})
    return simulation.compare_cases(cases)
@app.get('/api/jobs')
def jobs():
    return sorted(STORE.list()+RESEARCH.jobs(),key=lambda value:value['created'],reverse=True)[:100]
@app.get('/api/jobs/{id}')
def details(id:str):
    if RESEARCH.get(id):return RESEARCH.details(id)
    v=job(id);folder=run_dir(id);v['log']=(folder/'run.log').read_text(encoding='utf-8',errors='replace')[-50000:] if (folder/'run.log').exists() else '等待执行器领取任务…'
    v['artifacts']=[p.name for p in folder.glob('*') if p.is_file()] if folder.exists() else []
    v['events']=STORE.events(id)
    if v['state']=='SUCCEEDED':v['summary']=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    return v
@app.delete('/api/jobs/{id}')
def delete_task_files(id:str):
    with STATELOCK,RESEARCH.lock:
        value=job(id)
        if value['state'] in persistence.ACTIVE or id in PROCESSES or id in RESEARCH.processes:raise HTTPException(409,'请先停止任务并确认计算进程结束')
        if any(r['state']=='running' and any(t.get('arguments',{}).get('id')==id for t in r.get('trace',[])) for r in RESEARCH.runs.values()):raise HTTPException(409,'Agent 正在使用此任务，请先停止当前请求')
        try:task_files.remove(LOCAL/'runs',id)
        except (OSError,ValueError) as exc:raise HTTPException(409,'文件未成功删除，任务记录保留：'+str(exc)) from None
        with connect() as db:
            db.execute('DELETE FROM research_jobs WHERE id=?',(id,))
            db.execute('DELETE FROM job_events WHERE job_id=?',(id,))
            db.execute('DELETE FROM jobs WHERE id=?',(id,))
    return {'id':id,'deleted':True,'files_deleted':True,'recoverable':False}

@app.post('/api/jobs/{id}/open-folder')
def open_task_folder(id:str):
    job(id)
    try:path=task_files.reveal(LOCAL/'runs',id)
    except FileNotFoundError as exc:raise HTTPException(404,str(exc)) from None
    except (OSError,ValueError) as exc:raise HTTPException(409,str(exc)) from None
    return {'opened':True,'path':str(path)}

@app.post('/api/jobs/{id}/cancel')
def cancel(id:str):
    if RESEARCH.get(id):
        try:return RESEARCH.cancel(id)
        except ValueError as error:raise HTTPException(409,str(error)) from None
    with STATELOCK:
        value=job(id)
        if value['state'] not in persistence.ACTIVE:raise HTTPException(409,'任务已结束')
        if value['state']=='RUNNING' and value.get('claimed_by')!=WORKER_OWNER:raise HTTPException(503,'任务由另一执行器进程持有，当前进程不能确认停止；请管理员检查单进程部署。')
        CANCEL_REQUESTS.add(id)
        try:
            if not kill(id):
                STORE.set_paused(True)
                raise HTTPException(503,'取消尚未确认进程停止，队列已暂停；请管理员检查，任务没有被误标为已取消。')
            if not STORE.finish(id,'CANCELLED','用户取消任务，执行进程已停止或尚未启动。',owner=WORKER_OWNER):raise HTTPException(409,'任务已结束或已由其他执行器领取，请刷新状态。')
        finally:CANCEL_REQUESTS.discard(id)
    return {'cancelled':True}
@app.post('/api/queue/pause')
async def pause(request:Request):
    global PAUSED
    PAUSED=bool((await request.json()).get('paused'));STORE.set_paused(PAUSED);WORKER_WAKE.set();return {'paused':PAUSED}

@app.get('/api/queue/status')
def queue_status():
    with connect() as connection:counts={row['state']:row['count'] for row in connection.execute('SELECT state,COUNT(*) AS count FROM jobs GROUP BY state')}
    return {'backend':'sqlite_durable_v2','worker_active':WORKER_ACTIVE,'last_error':WORKER_ERROR,'paused':STORE.paused(),'counts':counts,'restart_policy':'QUEUED 保留；孤立 RUNNING 标为 INTERRUPTED 并暂停队列，管理员确认无残留进程后恢复。'}
@app.get('/api/jobs/{id}/artifact/{name}')
def artifact(id:str,name:str):
    job(id);folder=run_dir(id);path=(folder/name).resolve()
    if not path.is_relative_to(folder.resolve()) or not path.is_file():raise HTTPException(404)
    return FileResponse(path)
@app.get('/api/jobs/{id}/download')
def download(id:str):
    job(id);folder=run_dir(id);buff=io.BytesIO()
    with zipfile.ZipFile(buff,'w',zipfile.ZIP_DEFLATED) as z:
        for path in folder.glob('*'):
            if path.is_file():z.write(path,path.name)
    return Response(buff.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="ocean-{id}.zip"'})

def project_root():
    path=Path(config()['project_path']).resolve()
    if not path.is_dir():raise HTTPException(400,'项目目录不存在')
    return path
@app.get('/api/project/files')
def files():
    return project_browser.list_files(ROOT,project_root(),LOCAL,jobs())
@app.get('/api/project/file')
def read_file(path:str):
    return project_browser.read_file(ROOT,project_root(),LOCAL,path,job)

@app.get('/api/project/content')
def project_content(path:str):
    file,_=project_browser.resolve_file(ROOT,project_root(),LOCAL,path,job)
    return FileResponse(file)

class Chat(BaseModel):
    message:str=Field(min_length=1,max_length=12000)
    mode:Literal['chat','agent']='chat'
    session:str='default'
    knowledge_mode:Literal['course','general']='course'
    provider:str|None=None
    model:str|None=Field(default=None,max_length=160)
    context_budget:Literal['auto',4096,8192,16384,32768,65536,131072]='auto'
    @field_validator('context_budget',mode='before')
    @classmethod
    def budget_choice(cls,value):
        context_budget.resolve_budget(value);return value
@app.get('/api/chat/history')
def history(session:str='default'):
    with connect() as c:rows=c.execute('SELECT * FROM messages WHERE session=? ORDER BY id DESC LIMIT 40',(session,)).fetchall()
    result=[]
    for row in reversed(rows):
        item=dict(row);meta=json.loads(item.pop('metadata','{}') or '{}');result.append({**item,**meta})
    return result
@app.get('/api/knowledge/gaps')
def knowledge_gaps():
    path=kbfile('knowledge-gaps.json');return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
@app.post('/api/chat')
async def chat(body:Chat):
    cfg=config();catalog=models.catalog();provider=body.provider or cfg.get('provider','Qwen')
    entry=next((p for p in catalog['providers'] if p['id']==provider),None)
    if not entry:raise HTTPException(422,'未知供应商')
    saved=cfg if provider==cfg.get('provider') else models.profiles(config).get(provider,{})
    cfg={**cfg,**saved,'provider':provider,'base_url':saved.get('base_url') or entry['base_url'],'model':body.model or saved.get('model') or next(m['id'] for m in catalog['models'] if m['provider']==provider),'api_key':saved.get('api_key','')}
    models.validate_endpoint(provider,cfg['base_url']);evidence=search(body.message);policy=answer_policy.policy(evidence,body.knowledge_mode,body.mode,body.message);response_model=None;context_metadata=context_budget.inactive_context(body.context_budget)
    previous_history=history(body.session)
    if not evidence and body.mode!='agent':answer_policy.note_gap(kbfile('knowledge-gaps.json'),body.message)
    with connect() as c:c.execute('INSERT INTO messages(session,role,text,created) VALUES(?,?,?,?)',(body.session,'user',body.message,stamp()))
    def finish_reply(reply,used):
        metadata={'model_used':used,'model_provider':provider if used else None,'requested_model':cfg['model'] if used else None,'response_model':response_model,'requested_knowledge_mode':body.knowledge_mode,'knowledge_scope':policy['knowledge_scope'] if used else 'course','coverage_status':policy['coverage_status'],'coverage_notice':policy['coverage_notice'],'evidence_assessment':policy.get('evidence_assessment'),'evidence':evidence,'citations':knowledge.citations_for(evidence),'retrieval':knowledge.retrieval_status(),'context':context_metadata}
        with connect() as c:c.execute('INSERT INTO messages(session,role,text,created,metadata) VALUES(?,?,?,?,?)',(body.session,'assistant',reply,stamp(),json.dumps(metadata,ensure_ascii=False)))
        return {'reply':reply,'evidence_ids':[e['id'] for e in evidence],**metadata}
    if policy['coverage_status']=='missing_observation_data':
        return finish_reply(policy['coverage_notice'],False)
    elif not cfg.get('api_key'):
        reply=knowledge.format_no_model_answer(evidence)
        if body.mode=='agent':reply='Agent 当前接入文件列表与读取工具。云端项目分析需要 API Key；自动修改代码尚未实现。项目面板和模板仿真可直接使用。\n\n'+reply
        if body.knowledge_mode=='general':reply='模型一般知识需要先配置 API Key。当前仅提供课程与公开资料检索。\n\n'+reply
        # Describe the answer actually produced, separately from the requested
        # knowledge mode. With no key neither pretrained generation nor agent
        # file analysis took place; only retrieved course evidence is shown.
        policy={**policy,'knowledge_scope':'course','coverage_status':'course_evidence' if evidence else 'no_course_evidence','coverage_notice':'尚未配置模型 API Key；本次仅展示检索到的资料，未调用模型。' if evidence else '尚未配置模型 API Key，且未检索到课程依据；本次没有使用模型一般知识。'}
        used=False
    elif not policy['can_generate']:
        reply=policy['coverage_notice']+'\n这条问题已加入你的待补资料记录。';used=False
    else:
        models.validate_endpoint(cfg['provider'],cfg['base_url'])
        tools=[{'type':'function','function':{'name':'read_project_file','description':'读取已授权项目中的一个文本文件','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},{'type':'function','function':{'name':'list_project_files','description':'列出授权项目文件','parameters':{'type':'object','properties':{}}}}] if body.mode=='agent' else []
        system='你是海洋声学助手。明确假设与缺失条件，数字不得编造。当前仅允许检索知识与读取项目，不能宣称运行或修改过代码。'+policy['rule']+knowledge.answer_context([])
        try:packed=context_budget.build_context(question=body.message,system=system,evidence=evidence,history=previous_history,context_budget=body.context_budget,tools=tools)
        except context_budget.ContextBudgetError as error:raise HTTPException(422,str(error)) from None
        if body.knowledge_mode=='course' and body.mode!='agent' and not packed['evidence']:raise HTTPException(422,'检索到了课程资料，但所选预算无法保留必要依据，请调大上下文预算后重试；未调用模型。')
        msgs=packed['messages'];evidence=packed['evidence'];context_metadata=packed['context']
        policy=answer_policy.policy(evidence,body.knowledge_mode,body.mode,body.message)
        if not policy['can_generate']:return finish_reply(policy['coverage_notice'],False)
        provider_http_status=None
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                for turn in range(4):
                    context_metadata['estimated_input_tokens']=context_budget.assert_messages_budget(msgs,body.context_budget,tools)
                    payload=models.chat_payload(cfg,msgs,tools)
                    payload['max_tokens']=4096
                    r=await client.post(cfg['base_url'].rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+cfg['api_key']},json=payload)
                    if r.status_code!=200:
                        provider_http_status=r.status_code
                        raise RuntimeError('Model provider request rejected')
                    payload_result=r.json();context_metadata=context_budget.with_provider_usage(context_metadata,payload_result.get('usage'));context_metadata.update(provider_calls=turn+1,usage_scope='last_provider_request');response_model=payload_result.get('model');result=payload_result['choices'][0]['message'];calls=result.get('tool_calls')
                    if not calls:reply=result.get('content') or '模型未返回文字内容';break
                    msgs.append(result)
                    for call in calls:
                        try:
                            args=json.loads(call['function']['arguments']);value=files() if call['function']['name']=='list_project_files' else read_file(args['path']) if call['function']['name']=='read_project_file' else {'error':'不允许的工具'}
                        except Exception:value={'error':'工具参数不合法或文件无法读取；请核对工具名称、参数和授权项目范围。'}
                        msgs.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(value,ensure_ascii=False)})
                else:reply='已达到首版工具调用次数上限，请缩小问题范围。'
            used=True
        except context_budget.ContextBudgetError as error:
            raise HTTPException(422,str(error)) from None
        except httpx.TimeoutException:
            raise HTTPException(502,'连接模型供应商超时，请稍后重试；这不表示 API Key 无效。') from None
        except httpx.RequestError:
            raise HTTPException(502,'无法建立与模型供应商的网络连接，请检查网络和官方端点后重试。') from None
        except Exception:
            # Never include arbitrary exception text or a remote response body:
            # transports may echo Authorization headers and secret values.
            reasons={401:'密钥无效或地域不匹配',402:'余额或额度不足',403:'账户没有该模型权限',404:'模型或接口不存在',429:'请求频率或额度受限'}
            detail=f"模型供应商返回 HTTP {provider_http_status}：{reasons.get(provider_http_status,'请求未成功，请核对官方参数')}。" if provider_http_status is not None else '模型请求未完成或返回格式不兼容，请检查供应商配置后重试。'
            raise HTTPException(502,detail) from None
    return finish_reply(reply,used)

if (ROOT/'dist').exists():app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='frontend')
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8765)
