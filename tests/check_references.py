"""Check every source link used by course nodes; local requests only."""
import urllib.request,json,concurrent.futures
base='http://127.0.0.1:8765'
with urllib.request.urlopen(base+'/api/graph') as r:g=json.load(r)
urls=set()
for n in g['nodes']:
 for ref in n.get('references',[]):
  urls.add(ref['code_url'] if 'code_url' in ref else f"/api/source/{ref['source_id']}/page/{ref['pdf_page']}")
 for im in n['images']:
  if '.svg' in im['url']:urls.add(im['url'])
def verify(url):
 try:
  with urllib.request.urlopen(base+url,timeout=90) as response:
   data=response.read();assert data and response.status==200
   if '/page/' in url:assert data.startswith(b'\x89PNG')
  return None
 except Exception as error:return (url,str(error))
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:failures=[x for x in pool.map(verify,urls) if x]
assert not failures,failures
print(f'PASS: all {len(urls)} distinct textbook-page, source-code, and diagram URLs are readable')
