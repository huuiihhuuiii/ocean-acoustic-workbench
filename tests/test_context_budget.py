"""Offline context trimming and cross-runtime parity; no paid model request."""
import json
import shutil
import sqlite3
import subprocess
import sys
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
import test_local_chat_safety as chat_fixture

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import context_budget as cb

class ContextBudget(unittest.TestCase):
 def test_allowed_and_invalid_settings(self):
  self.assertEqual(cb.resolve_budget('auto'),32768)
  for size in cb.CONTEXT_BUDGETS:self.assertEqual(cb.resolve_budget(size),size)
  for size in [True,None,'4096',4096.0,1,1048576]:
   with self.subTest(size=size),self.assertRaises(cb.ContextBudgetError):cb.resolve_budget(size)
 def test_question_system_and_complete_history(self):
  history=[entry for i in range(20) for entry in [{'role':'user','text':f'question-{i}'+('x'*100)},{'role':'assistant','text':f'answer-{i}'+('y'*150)}]]
  small=cb.build_context(question='当前问题🌊',system='必须保留的系统说明',history=history,context_budget=4096)
  large=cb.build_context(question='当前问题🌊',system='必须保留的系统说明',history=history,context_budget=16384)
  self.assertEqual(small['messages'][-1]['content'],'当前问题🌊');self.assertTrue(small['messages'][0]['content'].startswith('必须保留的系统说明'))
  self.assertGreater(small['context']['dropped_history_messages'],0);self.assertEqual(small['context']['history_messages_used']%2,0)
  self.assertGreater(large['context']['history_messages_used'],small['context']['history_messages_used'])
  self.assertLessEqual(small['context']['estimated_input_tokens'],3072)
 def test_large_question_and_tool_result_are_rejected(self):
  with self.assertRaises(cb.ContextBudgetError):cb.build_context(question='海'*1500,system='系统',context_budget=4096)
  packed=cb.build_context(question='海'*1500,system='系统',context_budget=8192)
  self.assertEqual(packed['messages'][-1]['content'],'海'*1500)
  with self.assertRaises(cb.ContextBudgetError):cb.assert_messages_budget([*packed['messages'],{'role':'tool','content':'x'*10000}],8192)
 def test_last_old_turn_cannot_crowd_out_course_evidence(self):
  history=[{'role':'user','text':'x'*1400},{'role':'assistant','text':'y'*1300}]
  evidence=[{'id':'essential','source_id':'TEST','text':'可核查课程依据'*60,'conditions':'以实际资料为依据'}]
  history_alone=cb.build_context(question='当前问题',system='系统',history=history,context_budget=4096)
  self.assertEqual(history_alone['context']['history_messages_used'],2)
  packed=cb.build_context(question='当前问题',system='系统',history=history,evidence=evidence,context_budget=4096)
  self.assertEqual(packed['context']['history_messages_used'],0);self.assertEqual(packed['context']['dropped_history_messages'],2)
  self.assertEqual(len(packed['evidence']),1);self.assertEqual(packed['evidence'][0]['text'],evidence[0]['text'])
  self.assertFalse(packed['context']['evidence_truncated']);self.assertLessEqual(packed['context']['estimated_input_tokens'],3072)
 def test_evidence_clipping_preserves_formula_and_conditions(self):
  rows=[{'id':'first','source_id':'TEST','text':'原文🌊'*1500,'formula':'TL = -20 log10 |p|','conditions':'仅相干 FIELD 归一化压力。'},{'id':'dropped','source_id':'TEST','text':'low priority'}]
  packed=cb.build_context(question='解释 TL',system='系统',evidence=rows,context_budget=4096)
  self.assertEqual(len(packed['evidence']),1);self.assertTrue(packed['evidence'][0]['context_truncated'])
  self.assertEqual(packed['evidence'][0]['formula'],rows[0]['formula']);self.assertEqual(packed['evidence'][0]['conditions'],rows[0]['conditions'])
  self.assertNotIn('dropped',packed['messages'][0]['content']);self.assertEqual(rows[0]['text'],'原文🌊'*1500)
 def test_usage_is_measured_separately(self):
  context=cb.inactive_context(4096);self.assertFalse(context['applied']);self.assertIsNone(context['cached_tokens'])
  measured=cb.with_provider_usage(context,{'prompt_tokens':321,'prompt_cache_hit_tokens':120})
  self.assertEqual(measured['provider_prompt_tokens'],321);self.assertEqual(measured['cached_tokens'],120)
  self.assertIsNone(cb.with_provider_usage(context,{})['cached_tokens']);self.assertEqual(cb.with_provider_usage(context,{'prompt_tokens_details':{'cached_tokens':0}})['cached_tokens'],0)
 def test_python_and_cloud_algorithms_match_shared_unicode_fixture(self):
  executable=shutil.which('node')
  if not executable:self.skipTest('Node runtime not installed')
  module=(ROOT.parent/'ocean-acoustic-public/server/context-budget.mjs').as_uri()
  fixture={'question':'当前问题🌊','system':'必要系统说明','context_budget':4096,'evidence':[{'id':'first','source_id':'TEST','text':'原文🌊'*800,'formula':'TL','conditions':'归一化压力'},{'id':'second','source_id':'TEST','text':'低优先级'}],'history':[{'role':'user','text':'旧问题'},{'role':'assistant','text':'旧回答'}],'template':'function example\n'+('% 注释\n'*1000)}
  script="import{buildContext}from"+json.dumps(module)+";let input='';for await(const chunk of process.stdin)input+=chunk;process.stdout.write(JSON.stringify(buildContext(JSON.parse(input))));"
  cloud=json.loads(subprocess.run([executable,'--input-type=module','-e',script],input=json.dumps(fixture,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,check=True).stdout)
  self.assertEqual(cloud,cb.build_context(**fixture))

class ContextBudgetEndpoint(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.fixture=chat_fixture.LocalChatSafety();self.fixture.setUp()
  self.fixture.connection_config['api_key']=chat_fixture.TEST_KEY
 def tearDown(self):self.fixture.tearDown()
 def test_local_schema_rejects_coercible_but_invalid_choices(self):
  schema=self.fixture.namespace['Chat']
  for value in [True,'4096',4096.0,1,None]:
   with self.subTest(value=value),self.assertRaises(ValidationError):schema(message='测试',context_budget=value)
 async def test_large_question_stops_before_provider_transport(self):
  with patch.object(httpx,'AsyncClient',side_effect=AssertionError('Provider transport must not run')):
   with self.assertRaises(HTTPException) as caught:
    await self.fixture.namespace['chat'](self.fixture.namespace['Chat'](message='海'*1500,knowledge_mode='general',context_budget=4096))
  self.assertEqual(caught.exception.status_code,422);self.assertIn('调大',caught.exception.detail)
  self.assertNotIn(chat_fixture.TEST_KEY,caught.exception.detail)
 async def test_current_question_is_not_duplicated_and_usage_is_saved(self):
  observed=[]
  def history(session):
   with closing(sqlite3.connect(self.fixture.database)) as connection:
    return [{'role':role,'text':text} for role,text in connection.execute('SELECT role,text FROM messages WHERE session=? ORDER BY id',(session,))]
  self.fixture.namespace['history']=history
  class FakeClient:
   def __init__(self,**options):pass
   async def __aenter__(self):return self
   async def __aexit__(self,*args):return False
   async def post(self,*args,**options):
    observed.append(options['json']['messages'])
    return httpx.Response(200,json={'model':'qwen-test','choices':[{'message':{'content':'预算测试回复'}}],'usage':{'prompt_tokens':111,'prompt_tokens_details':{'cached_tokens':0}}})
  with patch.object(httpx,'AsyncClient',FakeClient):result=await self.fixture.ask(context_budget=4096)
  self.assertEqual(len(observed),1);self.assertEqual(sum(message.get('content')=='测试问题' for message in observed[0]),1)
  self.assertEqual(result['context']['provider_prompt_tokens'],111);self.assertEqual(result['context']['cached_tokens'],0)
  self.assertEqual(result['context']['history_messages_used'],0);self.assertLessEqual(result['context']['estimated_input_tokens'],3072)
  with closing(sqlite3.connect(self.fixture.database)) as connection:
   saved=json.loads(connection.execute("SELECT metadata FROM messages WHERE role='assistant'").fetchone()[0])
  self.assertEqual(saved['context'],result['context'])
 async def test_large_tool_result_cannot_trigger_a_second_provider_call(self):
  calls=[];self.fixture.namespace['read_file']=lambda path:{'path':path,'content':'x'*10000}
  class FakeClient:
   def __init__(self,**options):pass
   async def __aenter__(self):return self
   async def __aexit__(self,*args):return False
   async def post(self,*args,**options):
    calls.append(options['json'])
    if len(calls)>1:raise AssertionError('Oversized tool result must not reach provider')
    return httpx.Response(200,json={'model':'qwen-test','choices':[{'message':{'role':'assistant','tool_calls':[{'id':'test-call','type':'function','function':{'name':'read_project_file','arguments':'{"path":"fixture.m"}'}}]}}]})
  with patch.object(httpx,'AsyncClient',FakeClient):
   with self.assertRaises(HTTPException) as caught:await self.fixture.ask(mode='agent',context_budget=4096)
  self.assertEqual(caught.exception.status_code,422);self.assertEqual(len(calls),1)
  self.assertIn('工具结果',caught.exception.detail);self.assertNotIn(chat_fixture.TEST_KEY,caught.exception.detail)

if __name__=='__main__':unittest.main()
