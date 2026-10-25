"""Page-level retrieval over authorized, locally cached course PDFs."""
import json,re,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCAL=Path(os.environ.get('OCEAN_RUNTIME_DIR',str(ROOT/'.local')))
INDEX=LOCAL/'kb/material_pages.json'
_cache=None
_version=None

def pages():
    global _cache,_version
    if not INDEX.exists():return []
    version=INDEX.stat().st_mtime_ns
    if version!=_version:
        _cache=json.loads(INDEX.read_text(encoding='utf-8'))['pages'];_version=version
    return _cache

def catalog():
    registry=json.loads((LOCAL/'kb/source_registry.json').read_text(encoding='utf-8'))['sources']
    counts={}
    for p in pages():counts[p['source_id']]=counts.get(p['source_id'],0)+1
    return [{'source_id':s['id'],'name':s['name'],'indexed_pages':counts.get(s['id'],0),'pdf_pages':s.get('pdf_pages'),'available':(LOCAL/'sources'/(s['id']+'.pdf')).exists(),'text_status':'可检索提取文字' if counts.get(s['id']) else '未建立可检索文字；扫描版需OCR或查看原页'} for s in registry]

def search(query,source_id=None):
    query=query.strip().lower()[:200]
    terms=re.findall(r'[a-z0-9_-]+|[\u4e00-\u9fff]+',query)
    aliases={'简正波':'normal mode','波数积分':'wavenumber integration','射线':'ray tracing','声速剖面':'sound speed profile','传播损失':'transmission loss','抛物方程':'parabolic equation','收敛':'convergence','海底':'bottom','声道':'sound channel'}
    terms+= [english for chinese,english in aliases.items() if chinese in query]
    if not terms:return {'matches':[],'note':'请输入专业关键词'}
    scored=[]
    for p in pages():
        if source_id and p['source_id']!=source_id:continue
        text=p['text'].lower();score=sum(text.count(t)*min(len(t),8) for t in terms)
        if score:
            pos=min((text.find(t) for t in terms if t in text),default=0)
            scored.append((score,p,pos))
    scored.sort(key=lambda r:(-r[0],r[1]['source_id'],r[1]['page']))
    return {'matches':[{**{k:p[k] for k in ('source_id','name','page')},'excerpt':p['text'][max(0,pos-180):max(0,pos-180)+1200],'url':f"/api/source/{p['source_id']}#page={p['page']}"} for score,p,pos in scored[:6]],'source_filter':source_id,'total_matching_pages':len(scored),'expanded_terms':terms,'note':'仅展示排名前6页；某来源未出现在这些结果中不代表全文未命中。扫描版不参与文字搜索，摘录用于定位，请读取原页核实公式。'}

def read(source_id,page):
    for p in pages():
        if p['source_id']==source_id and p['page']==page:
            return {**p,'text':p['text'][:12000],'truncated':len(p['text'])>12000,'url':f'/api/source/{source_id}#page={page}','note':'PDF提取文字可能丢失公式结构；可查看原页图片核对。','image_url':f'/api/source/{source_id}/page/{page}'}
    source=next((s for s in catalog() if s['source_id']==source_id),None)
    if source and source['available'] and isinstance(page,int) and page>=1 and page<=int(source.get('pdf_pages') or 0):
        return {'source_id':source_id,'page':page,'name':source['name'],'text':'','note':'此页没有可检索文字。需要OCR或人工查看原页；不能声称已经读取公式。','url':f'/api/source/{source_id}#page={page}','image_url':f'/api/source/{source_id}/page/{page}'}
    return {'error':'来源或页码不可用，请先查看 list_materials。'}
