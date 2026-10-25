"""Integration checks against the running local app; no cloud API calls."""
import json, urllib.request, urllib.error, urllib.parse, io, zipfile, concurrent.futures
BASE='http://127.0.0.1:8765/api'
def request(path,body=None,headers=None):
    r=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(r,timeout=30) as response:return response.status,response.read()
    except urllib.error.HTTPError as e:return e.code,e.read()
def expect(path,status,body=None,headers=None):
    code,data=request(path,body,headers);assert code==status,(path,code,data[:300]);return data
health=json.loads(expect('/health',200));assert health['matlab_available'] and health['solver_available']
graph=json.loads(expect('/graph',200));assert len(graph['nodes'])==53 and len(graph['edges'])==126
ids={n['id'] for n in graph['nodes']};assert all(e['source'] in ids and e['target'] in ids for e in graph['edges'])
points=[n for n in graph['nodes'] if n['kind']=='knowledge'];assert len(points)==46
assert all(n['references'] and n['key_points'] and n['overview'] and n['images'] for n in points)
hierarchy=[e for e in graph['edges'] if e['group']=='hierarchy'];assert len(hierarchy)==52
assert all(sum(e['target']==n['id'] for e in hierarchy)==1 for n in graph['nodes'] if n['id']!='course')
reachable={'acoustic_pressure'}
for _ in points:
    for e in graph['edges']:
        if e['group']=='related' and (e['source'] in reachable or e['target'] in reachable):reachable.update([e['source'],e['target']])
assert reachable=={n['id'] for n in points}
path=json.loads(expect('/graph/path?source=sound_speed_profile&target=transmission_loss',200));assert path['nodes'][0]=='sound_speed_profile' and path['nodes'][-1]=='transmission_loss'
assert all(next(e for e in graph['edges'] if e['id']==id)['group']=='related' for id in path['edges'])
expect('/graph/path?source=invalid&target=transmission_loss',422)
retrieved=json.loads(expect('/knowledge/search?q='+urllib.parse.quote('请解释 Munk 理想剖面，并说明适用条件'),200))
assert retrieved[0]['node_id']=='munk_profile'
assert {c['node_id'] for c in retrieved if c['node_id']} <= {'munk_profile','deep_sound_channel','env_file'}
assert retrieved[0]['related_triples']
assert any(c['node_id']=='munk_profile' and c['formula'] for c in retrieved)
assert all(c['source_id'] and (c.get('pdf_page') or c.get('locator')) for c in retrieved)
assert any(c.get('evidence_type')=='source_excerpt' and c['pdf_page']>38 for c in retrieved)
assert json.loads(expect('/knowledge/search?q=zzzznonexistent',200))==[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    images=list(pool.map(lambda p:expect('/source/S17/page/'+str(p),200),[375,376,356,357,359,478]))
    assert all(img.startswith(b'\x89PNG') for img in images)
expect('/knowledge/code?node=env_file&reference=0',200);expect('/knowledge/code?node=env_file&reference=2',200)
expect('/knowledge/code?node=unknown&reference=0',404)
catalog=json.loads(expect('/models/catalog',200));assert len(catalog['providers'])==4 and len(catalog['models'])==16
flash=next(m for m in catalog['models'] if m['key']=='DeepSeek:deepseek-flash');assert flash['name']=='DeepSeek-V4.1-Flash'
profiles=json.loads(expect('/models/profiles',200));assert all('api_key' not in p for p in profiles.values())
expect('/models/test',422,{'provider':'DeepSeek','model':'deepseek-flash'})
expect('/models/list',422,{'provider':'DeepSeek','model':'deepseek-flash'})
expect('/models/test',422,{'provider':'DeepSeek','model':'deepseek-flash','base_url':'https://example.org','api_key':'test-only'})
expect('/source/S17/page/357',200);expect('/source/S17/page/999999',404)
files=json.loads(expect('/project/files',200));assert any(f['path']=='run_ocean_case.m' for f in files['files'])
expect('/project/file?path=run_ocean_case.m',200);expect('/project/file?path=../config.json',403)
expect('/plans/preview',422,{'frequencies_hz':[0]})
expect('/plans/preview',422,{'source_depths_m':[5000]})
expect('/plans/preview',422,{'range_min_km':20,'range_max_km':10})
expect('/plans/preview',422,{'template':'unverified'})
expect('/plans/preview',403,{}, {'Origin':'https://example.org'})
p=json.loads(expect('/plans/preview',200,{'frequencies_hz':[50,100],'source_depths_m':[500,1000]}));assert p['case_count']==4
cfg=json.loads(expect('/config',200));assert 'api_key' not in cfg
if not cfg['api_key_set']:
    reply=json.loads(expect('/chat',200,{'message':'声源深度','session':'integration-check','mode':'agent'}));assert reply['model_used'] is False and reply['evidence_ids']
jobs=json.loads(expect('/jobs',200));done=[j for j in jobs if j['state']=='SUCCEEDED'];assert done
id=done[0]['id'];detail=json.loads(expect('/jobs/'+id,200));assert detail['summary']['shape']==[detail['plan']['depth_points'],detail['plan']['range_points']]
archive=zipfile.ZipFile(io.BytesIO(expect('/jobs/'+id+'/download',200)))
assert {'result.json','case.env','case.flp','run.log','tl_map.png','tl_curve.png'}<=set(archive.namelist())
print('PASS: 46 connected knowledge points, 126 typed relationships, association paths, concurrent PDF pages, code sources, 16 model presets, redacted profiles, provider-domain validation, project boundaries, invalid plans, cross-origin guard, no-key retrieval, real result and download')
