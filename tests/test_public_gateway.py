"""Actual gateway routes, temporary DBs and a fake private node; no network.

Only top-level runtime/secret-path assignments are replaced. Definitions,
middleware, route registration and database initialization use the real source.
The fake node uses the actual durable JobStore for idempotent receipts.
"""
import ast
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from persistence import JobStore

PLAN={'template':'munk_5000m','frequencies_hz':[50],'source_depths_m':[1000],'receiver_depth_m':1000,'range_min_km':1,'range_max_km':10,'range_points':101,'depth_points':101}
REAL_HTTP_CLIENT=httpx.AsyncClient

class PublicGateway(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.directory=tempfile.TemporaryDirectory();self.local=Path(self.directory.name)
  self.node=JobStore(self.local/'workbench.sqlite3');self.node.migrate();self.calls=[];self.external=[];self.fail=None
  source=ast.parse((ROOT/'backend/public_gateway.py').read_text(encoding='utf-8-sig'));nodes=[]
  for item in source.body:
   if isinstance(item,ast.Import) and any(name.name in ('knowledge','models') for name in item.names):continue
   if isinstance(item,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.AsyncFunctionDef,ast.With)):nodes.append(item)
   elif isinstance(item,ast.Assign) and any(isinstance(target,ast.Name) and target.id in ('profiles','limits','submit_lock','app') for target in item.targets):nodes.append(item)
  self.namespace={'__name__':'isolated_public_gateway','__file__':str(ROOT/'backend/public_gateway.py'),'ROOT':ROOT,'LOCAL':self.local,'DB':self.local/'public-visitors.sqlite3','SECRET':'TEST-ONLY-NOT-REAL-GATEWAY-SECRET','ORIGIN':'https://course.test','PRIVATE':'http://127.0.0.1:8765','knowledge':SimpleNamespace(),'models':SimpleNamespace()}
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/'backend/public_gateway.py'),'exec'),self.namespace)
  self.client=REAL_HTTP_CLIENT(transport=httpx.ASGITransport(app=self.namespace['app'],raise_app_exceptions=False),base_url='https://course.test')
  test=self
  class FakeNodeClient:
   def __init__(self,**kwargs):pass
   async def __aenter__(self):return self
   async def __aexit__(self,*args):return False
   async def request(self,method,url,**kwargs):return await test.private(method,url,**kwargs)
   async def post(self,url,**kwargs):return await test.private('POST',url,**kwargs)
   async def get(self,url,**kwargs):return await test.private('GET',url,**kwargs)
  self.transport_patch=patch.object(httpx,'AsyncClient',FakeNodeClient);self.transport_patch.start()
 async def asyncTearDown(self):
  await self.client.aclose();self.transport_patch.stop();self.directory.cleanup()
 async def private(self,method,url,**options):
  path=httpx.URL(url).path;payload=options.get('json')
  if payload is None and options.get('content'):payload=json.loads(options['content'])
  self.calls.append({'method':method,'path':path,'headers':dict(options.get('headers',{})),'payload':payload})
  if path=='/api/plans/preview':
   if not isinstance(payload,dict):return httpx.Response(422,json={'detail':'invalid plan fixture'})
   return httpx.Response(200,json={'plan':{**PLAN,**payload}})
  if path=='/api/jobs' and method=='GET':return httpx.Response(200,json=self.node.list()+self.external)
  if path=='/api/jobs' and method=='POST':
   mode=self.fail;self.fail=None
   if mode=='failure_before_commit':return httpx.Response(500,json={'detail':'fixture failure before creation'})
   if mode=='timeout_before_commit':raise httpx.ReadTimeout('synthetic node interruption')
   headers=options.get('headers',{});value=self.node.submit(payload,scope=headers.get('X-Ocean-Submission-Scope','local'),idempotency_key=headers.get('Idempotency-Key'))
   if mode=='timeout_after_commit':raise httpx.ReadTimeout('synthetic response lost after commit')
   if mode=='failure_after_commit':return httpx.Response(500,json={'detail':'synthetic response failure after commit'})
   return httpx.Response(200,json=value)
  if path=='/api/jobs/compare':return httpx.Response(200,json={'comparable':True,'ids':payload['ids'],'execution_started':False})
  if path.startswith('/api/jobs/'):
   value=self.node.get(path.split('/')[3]);return httpx.Response(200 if value else 404,json=value or {'detail':'missing'})
  raise AssertionError('Unapproved fixture endpoint '+path)
 async def call(self,visitor,path='/api/jobs',body=None,key=None,method='POST',raw=None):
  headers={'x-ocean-gateway':self.namespace['SECRET'],'origin':'https://course.test','cookie':'ocean_visitor='+visitor*64}
  if key:headers['idempotency-key']=key
  return await self.client.request(method,path,headers=headers,**({'content':raw} if raw is not None else {'json':body} if body is not None else {}))
 async def create(self,visitor='A',key='request-0001',plan=None):
  response=await self.call(visitor,body=plan or PLAN,key=key);self.assertEqual(response.status_code,200,response.text);return response.json()
 def full_queue(self):self.external=[{'id':f'{index:012x}','state':'RUNNING'} for index in range(16)]

 async def test_visitors_without_request_keys_never_share_an_active_local_batch(self):
  a=await self.create('A',key=None);b=await self.create('B',key=None)
  self.assertNotEqual(a['ids'],b['ids']);self.assertEqual(len(self.node.list()),2)
  self.assertEqual((await self.call('B',f"/api/jobs/{a['ids'][0]}",method='GET')).status_code,404)
  self.assertEqual((await self.call('B',f"/api/jobs/{b['ids'][0]}",method='GET')).status_code,200)
 async def test_cached_replay_occurs_before_quota_and_own_active_batch_check(self):
  a=await self.create();before=sum(row['method']=='POST' and row['path']=='/api/jobs' for row in self.calls);self.full_queue()
  repeated=await self.call('A',body=PLAN,key='request-0001');self.assertEqual(repeated.status_code,200,repeated.text);self.assertEqual(repeated.json()['ids'],a['ids']);self.assertTrue(repeated.json()['reused'])
  self.assertEqual(sum(row['method']=='POST' and row['path']=='/api/jobs' for row in self.calls),before)
 async def test_reusing_request_key_with_different_body_conflicts(self):
  await self.create();response=await self.call('A',body={**PLAN,'receiver_depth_m':900},key='request-0001')
  self.assertEqual(response.status_code,409);self.assertEqual(len(self.node.list()),1)
 async def test_same_request_key_on_another_visitor_is_not_a_receipt_leak(self):
  a=await self.create('A');b=await self.create('B');self.assertNotEqual(a['ids'],b['ids'])
  sent=[row['headers'] for row in self.calls if row['path']=='/api/jobs' and row['method']=='POST'];self.assertNotEqual(sent[0]['Idempotency-Key'],sent[1]['Idempotency-Key']);self.assertNotEqual(sent[0]['X-Ocean-Submission-Scope'],sent[1]['X-Ocean-Submission-Scope'])
 async def test_confirmed_failure_without_commit_clears_pending_and_cannot_bypass_quota(self):
  self.fail='failure_before_commit';failed=await self.call('A',body=PLAN,key='request-0001');self.assertEqual(failed.status_code,500)
  with self.namespace['connect']() as connection:self.assertEqual(connection.execute('SELECT COUNT(*) FROM public_submissions').fetchone()[0],0)
  self.full_queue();retried=await self.call('A',body=PLAN,key='request-0001');self.assertEqual(retried.status_code,429);self.assertEqual(self.node.list(),[])
 async def test_unconfirmed_failure_without_receipt_keeps_key_and_respects_quota(self):
  self.fail='timeout_before_commit';failed=await self.call('A',body=PLAN,key='request-0001');self.assertEqual(failed.status_code,503)
  self.full_queue();retried=await self.call('A',body=PLAN,key='request-0001');self.assertEqual(retried.status_code,429)
  with self.namespace['connect']() as connection:
   row=connection.execute('SELECT response FROM public_submissions').fetchone();self.assertIsNotNone(row);self.assertIsNone(row['response'])
  self.external=[];recovered=await self.create();self.assertEqual(len(recovered['ids']),1);self.assertEqual(len(self.node.list()),1)
 async def test_lost_response_recovers_owned_jobs_from_actual_local_receipt_even_when_full(self):
  self.fail='timeout_after_commit';failed=await self.call('A',body=PLAN,key='request-0001');self.assertEqual(failed.status_code,503);self.assertEqual(len(self.node.list()),1)
  self.full_queue();recovered=await self.create();self.assertTrue(recovered['reused']);self.assertEqual(recovered['ids'],[self.node.list()[0]['id']]);self.assertEqual(len(self.node.list()),1)
  self.assertEqual((await self.call('A',f"/api/jobs/{recovered['ids'][0]}",method='GET')).status_code,200);self.assertEqual((await self.call('B',f"/api/jobs/{recovered['ids'][0]}",method='GET')).status_code,404)
 async def test_explicit_response_error_after_commit_recovers_without_submitting_twice(self):
  self.fail='failure_after_commit';result=await self.create();self.assertTrue(result['reused']);self.assertEqual(len(self.node.list()),1)
 async def test_local_receipt_hash_and_ids_are_validated(self):
  self.fail='timeout_after_commit';await self.call('A',body=PLAN,key='request-0001')
  with self.node.connection() as connection:connection.execute("UPDATE submissions SET plan_sha256='not-the-request'")
  self.assertEqual((await self.call('A',body=PLAN,key='request-0001')).status_code,409)
  fingerprint=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  with self.node.connection() as connection:connection.execute('UPDATE submissions SET plan_sha256=?,ids=?',(fingerprint,json.dumps(['../invalid'])))
  self.assertEqual((await self.call('A',body=PLAN,key='request-0001')).status_code,503)
 async def test_owned_comparison_checks_every_id_and_proxies_only_authorized_pairs(self):
  a=await self.create('A');b=await self.create('B');self.node.finish(a['ids'][0],'CANCELLED');second=await self.create('A',key='request-0002',plan={**PLAN,'receiver_depth_m':900})
  forbidden=await self.call('A','/api/jobs/compare',body={'ids':[a['ids'][0],b['ids'][0]]});self.assertEqual(forbidden.status_code,404)
  allowed=await self.call('A','/api/jobs/compare',body={'ids':[a['ids'][0],second['ids'][0]]});self.assertEqual(allowed.status_code,200,allowed.text)
  comparisons=[row for row in self.calls if row['path']=='/api/jobs/compare'];self.assertEqual(len(comparisons),1)
 async def test_invalid_comparison_json_and_id_shapes_never_return_500(self):
  invalid=[[],None,'text',{'ids':{}},{'ids':[{},[]]},{'ids':[True,'aaaaaaaaaaaa']},{'ids':['aaaaaaaaaaaa','aaaaaaaaaaaa']},{'ids':['../config.json','bbbbbbbbbbbb']},{'ids':['a']},{'ids':['a'*12,'b'*12],'command':'unsafe'}]
  for value in invalid:
   with self.subTest(value=value):
    response=await self.call('A','/api/jobs/compare',raw=json.dumps(value));self.assertEqual(response.status_code,422,response.text)
  response=await self.call('A','/api/jobs/compare',raw='{broken');self.assertEqual(response.status_code,422)
 async def test_concurrent_retries_create_only_one_batch_and_connections_close(self):
  results=await asyncio.gather(*[self.call('A',body=PLAN,key='same-parallel-request') for _ in range(8)])
  self.assertTrue(all(response.status_code==200 for response in results),[response.text for response in results]);self.assertEqual(len({tuple(response.json()['ids']) for response in results}),1);self.assertEqual(len(self.node.list()),1)
  with self.namespace['connect']() as connection:connection.execute('SELECT 1')
  with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
 async def test_readonly_receipt_connection_is_closed(self):
  original=sqlite3.connect;receipts=[]
  def capture(*args,**kwargs):
   connection=original(*args,**kwargs)
   if kwargs.get('uri') and 'mode=ro' in str(args[0]):receipts.append(connection)
   return connection
  with patch.object(sqlite3,'connect',side_effect=capture):await self.create()
  self.assertTrue(receipts)
  for connection in receipts:
   with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
 async def test_unreadable_receipt_keeps_pending_and_does_not_blindly_resubmit(self):
  self.fail='timeout_before_commit';await self.call('A',body=PLAN,key='request-0001');original=sqlite3.connect
  def unreadable(*args,**kwargs):
   if kwargs.get('uri') and 'mode=ro' in str(args[0]):raise sqlite3.OperationalError('TEST-ONLY-PRIVATE-ERROR')
   return original(*args,**kwargs)
  with patch.object(sqlite3,'connect',side_effect=unreadable):response=await self.call('A',body=PLAN,key='request-0001')
  self.assertEqual(response.status_code,503);self.assertNotIn('TEST-ONLY-PRIVATE-ERROR',response.text);self.assertEqual(self.node.list(),[])
  with self.namespace['connect']() as connection:self.assertIsNotNone(connection.execute('SELECT response FROM public_submissions').fetchone())

if __name__=='__main__':unittest.main()
