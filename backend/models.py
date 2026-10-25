import json
from pathlib import Path
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local'
def catalog():return json.loads((ROOT/'backend/data/model_catalog.json').read_text(encoding='utf-8'))
def profiles(config):
    path=LOCAL/'model-profiles.json'
    saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    current=config()
    if current.get('provider'):
        saved[current['provider']]={k:current.get(k,'') for k in ['base_url','model','api_key']}
    return saved
def public_profiles(config):
    return {k:{'base_url':v.get('base_url',''),'model':v.get('model',''),'api_key_set':bool(v.get('api_key'))} for k,v in profiles(config).items()}
def store_profile(cfg):
    path=LOCAL/'model-profiles.json';saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    saved[cfg['provider']]={k:cfg.get(k,'') for k in ['base_url','model','api_key']}
    path.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
def request_options(provider,model):
    row=next((x for x in catalog()['models'] if x['provider']==provider and x['id']==model),None)
    return dict(row['request_options']) if row else {}
def chat_payload(cfg,messages,tools=None):
    body={'model':cfg['model'],'messages':messages,**request_options(cfg['provider'],cfg['model'])}
    if tools:body['tools']=tools
    return body
def validate_endpoint(provider,base):
    url=urlparse(base)
    if url.scheme!='https' or not url.hostname:raise HTTPException(422,'模型地址必须为有效 HTTPS 地址')
    allowed={'DeepSeek':lambda h:h=='api.deepseek.com','Kimi':lambda h:h in ['api.moonshot.cn','api.moonshot.ai'],'GLM':lambda h:h=='open.bigmodel.cn','Qwen':lambda h:h in ['dashscope.aliyuncs.com','dashscope-us.aliyuncs.com','dashscope-intl.aliyuncs.com'] or h.endswith('.maas.aliyuncs.com')}
    if provider not in allowed or not allowed[provider](url.hostname):raise HTTPException(422,'地址与供应商不匹配，请核对官方 API 域名')
def select_connection(body,config):
    provider=body.get('provider') or config().get('provider')
    known=next((p for p in catalog()['providers'] if p['id']==provider),None)
    if not known:raise HTTPException(422,'请选择已登记的 API 供应商')
    saved=profiles(config).get(provider,{})
    base=body.get('base_url') or saved.get('base_url') or known['base_url']
    model=body.get('model') or saved.get('model')
    key=body.get('api_key') or saved.get('api_key')
    if not key:raise HTTPException(422,'请先填写该供应商的 API Key，或保存该供应商配置')
    if not model:raise HTTPException(422,'请选择具体模型')
    validate_endpoint(provider,base)
    return {'provider':provider,'base_url':base.rstrip('/'),'model':model,'api_key':key}
def raise_remote(response):
    if response.status_code==200:return
    names={401:'密钥无效或地域不匹配',402:'余额或额度不足',403:'账户无权限访问该模型',404:'模型或接口不存在',429:'请求频率或额度受限'}
    raise HTTPException(502,f"供应商返回 HTTP {response.status_code}：{names.get(response.status_code,'请求未成功，请核对官方参数与服务状态')}")
async def test_connection(body,config):
    cfg=select_connection(body,config)
    async with httpx.AsyncClient(timeout=90,follow_redirects=False) as client:
        try:
            payload=chat_payload(cfg,[{'role':'user','content':'Reply with OK.'}]);payload['max_tokens']=256
            r=await client.post(cfg['base_url']+'/chat/completions',headers={'Authorization':'Bearer '+cfg['api_key']},json=payload)
        except httpx.RequestError:raise HTTPException(502,'无法连接供应商，请检查网络和接口地址')
    raise_remote(r)
    try:
        result=r.json();choice=result['choices'][0];message=choice['message'];assert isinstance(message,dict)
    except (ValueError,KeyError,IndexError,AssertionError):raise HTTPException(502,'供应商返回格式不兼容 Chat Completions')
    # A successful HTTP test proves acceptance of a request; it does not certify agent tools.
    return {'ok':True,'provider':cfg['provider'],'requested_model':cfg['model'],'response_model':result.get('model',cfg['model']),'reply':(message.get('content') or '')[:200],'usage':result.get('usage',{}),'note':'当前模型调用已通过；不表示项目工具调用或视觉能力已经验证。'}
async def list_account_models(body,config):
    cfg=select_connection(body,config)
    async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
        try:r=await client.get(cfg['base_url']+'/models',headers={'Authorization':'Bearer '+cfg['api_key']})
        except httpx.RequestError:raise HTTPException(502,'无法连接供应商模型列表接口')
    if r.status_code==404:raise HTTPException(502,'该供应商未在此地址提供标准 /models 接口，可使用具体模型测试调用')
    raise_remote(r)
    try:rows=r.json()['data'];ids=[str(x['id']) for x in rows][:500]
    except (KeyError,TypeError,ValueError):raise HTTPException(502,'模型列表格式不兼容')
    return {'ids':ids,'selected_listed':cfg['model'] in ids,'note':'模型列表表示账户接口返回；实际调用仍取决于额度和权限。'}
