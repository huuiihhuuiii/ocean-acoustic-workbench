"""Run real FastAPI routes against an isolated runtime, never real MATLAB."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
import science
from test_science import fixture
from test_simulation import ENV

PLAN={'template':'munk_5000m','frequencies_hz':[50],'source_depths_m':[1000],'receiver_depth_m':1000,'range_min_km':1,'range_max_km':10,'range_points':101,'depth_points':101}

class SimulationAPI(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.runtime=Path(self.directory.name)
  self.environment=patch.dict(os.environ,{'OCEAN_RUNTIME_DIR':str(self.runtime),'OCEAN_DISABLE_WORKER':'1','OCEAN_DISABLE_PUBLIC_REFRESH':'1'});self.environment.start()
  self.processes=patch('subprocess.Popen',side_effect=AssertionError('No real process may start'));self.processes.start()
  spec=importlib.util.spec_from_file_location('isolated_simulation_'+uuid.uuid4().hex,ROOT/'backend/app.py');self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
  self.client_context=TestClient(self.module.app);self.client=self.client_context.__enter__()
 def tearDown(self):
  self.client_context.__exit__(None,None,None);self.processes.stop();self.environment.stop();self.directory.cleanup()
 def test_draft_preview_never_enqueues_and_reports_explicit_units(self):
  response=self.client.post('/api/plans/draft',json={'message':'Munk 频率0.05kHz 源深1km 接收深度1000m 距离1-10km'})
  self.assertEqual(response.status_code,200,response.text);draft=response.json();self.assertTrue(draft['ready_for_preview'],draft)
  self.assertEqual(draft['draft_plan']['frequencies_hz'],[50]);self.assertEqual(self.client.post('/api/plans/preview',json=draft['draft_plan']).status_code,200)
  self.assertEqual(self.client.get('/api/jobs').json(),[]);self.assertFalse(draft['execution_started'])
 def test_missing_and_out_of_range_are_reviewable_not_silently_defaulted(self):
  missing=self.client.post('/api/plans/draft',json={'message':'Munk 50Hz'}).json();self.assertFalse(missing['ready_for_preview']);self.assertNotIn('source_depths_m',missing['draft_plan'])
  invalid=self.client.post('/api/plans/draft',json={'message':'Munk 频率1000Hz 源深6000m 接收深度1000m 距离1-10km'}).json();self.assertFalse(invalid['ready_for_preview']);self.assertTrue(invalid['validation_errors'])
  self.assertEqual(self.client.post('/api/plans/draft',json={'message':'Munk','command':'unsafe'}).status_code,422)
 def test_same_submission_replays_but_changed_parameters_conflict(self):
  headers={'Idempotency-Key':'ui-request-0001'};first=self.client.post('/api/jobs',json=PLAN,headers=headers);second=self.client.post('/api/jobs',json=PLAN,headers=headers)
  self.assertEqual(first.status_code,200,first.text);self.assertEqual(first.json()['ids'],second.json()['ids']);self.assertTrue(second.json()['reused'])
  changed=self.client.post('/api/jobs',json={**PLAN,'receiver_depth_m':900},headers=headers);self.assertEqual(changed.status_code,409);self.assertEqual(len(self.client.get('/api/jobs').json()),1)
  status=self.client.get('/api/queue/status').json();self.assertEqual(status['backend'],'sqlite_durable_v2');self.assertFalse(status['worker_active']);self.assertEqual(status['counts']['QUEUED'],1)
 def test_local_scope_header_separates_two_visitor_batches(self):
  values=[self.client.post('/api/jobs',json=PLAN,headers={'Idempotency-Key':'ui-request-0001','X-Ocean-Submission-Scope':scope}).json() for scope in ['visitor-a','visitor-b']]
  self.assertNotEqual(values[0]['ids'],values[1]['ids'])
 def test_invalid_plan_or_idempotency_never_creates_partial_batch(self):
  for body,headers in [({**PLAN,'frequencies_hz':[50,0]},{}),(PLAN,{'Idempotency-Key':'bad'}),({**PLAN,'command':'system()'}, {})]:
   self.assertEqual(self.client.post('/api/jobs',json=body,headers=headers).status_code,422)
  self.assertEqual(self.client.get('/api/jobs').json(),[])
 def test_cancelled_job_cannot_be_overwritten_by_executor(self):
  job_id=self.client.post('/api/jobs',json=PLAN).json()['ids'][0];self.module.STORE.claim_next(self.module.WORKER_OWNER)
  self.assertEqual(self.client.post(f'/api/jobs/{job_id}/cancel').status_code,200);self.assertFalse(self.module.STORE.finish(job_id,'SUCCEEDED',owner=self.module.WORKER_OWNER))
  detail=self.client.get(f'/api/jobs/{job_id}').json();self.assertEqual(detail['state'],'CANCELLED');self.assertEqual([row['state'] for row in detail['events']],['QUEUED','RUNNING','CANCELLED'])
 def test_executor_loop_claims_persistent_rows_with_a_fake_execution(self):
  job_id=self.client.post('/api/jobs',json=PLAN).json()['ids'][0];seen=[]
  def fake_execute(row):
   seen.append(row['id']);self.module.STORE.finish(row['id'],'SUCCEEDED',owner=self.module.WORKER_OWNER);self.module.WORKER_STOP.set()
  with patch.object(self.module,'execute_job',side_effect=fake_execute):
   thread=threading.Thread(target=self.module.worker);thread.start();thread.join(timeout=3)
   if thread.is_alive():self.module.WORKER_STOP.set();self.module.WORKER_WAKE.set();thread.join(timeout=3)
  self.assertFalse(thread.is_alive());self.assertEqual(seen,[job_id]);self.assertEqual(self.module.STORE.get(job_id)['state'],'SUCCEEDED');self.assertFalse(self.module.WORKER_ACTIVE)
 def test_failed_process_stop_pauses_queue_without_faking_cancelled_state(self):
  job_id=self.client.post('/api/jobs',json=PLAN).json()['ids'][0];self.module.STORE.claim_next(self.module.WORKER_OWNER)
  with patch.object(self.module,'kill',return_value=False):response=self.client.post(f'/api/jobs/{job_id}/cancel')
  self.assertEqual(response.status_code,503);self.assertEqual(self.module.STORE.get(job_id)['state'],'RUNNING');self.assertTrue(self.module.STORE.paused())
 def test_other_process_cannot_report_a_foreign_worker_job_cancelled(self):
  job_id=self.client.post('/api/jobs',json=PLAN).json()['ids'][0];self.module.STORE.claim_next('another-worker')
  with patch.object(self.module,'kill',side_effect=AssertionError('Foreign process must not guess another process stopped')):response=self.client.post(f'/api/jobs/{job_id}/cancel')
  self.assertEqual(response.status_code,503);self.assertEqual(self.module.STORE.get(job_id)['state'],'RUNNING')
 def create_completed_fixture(self,frequency=50,environment=ENV):
  plan,result=fixture();plan.update(frequency_hz=frequency,frequencies_hz=[frequency]);result['frequency_hz']=frequency
  submitted=self.module.STORE.submit(plan,idempotency_key='fixture-'+uuid.uuid4().hex);row=self.module.STORE.claim_next('fixture')
  self.assertEqual(row['id'],submitted['ids'][0]);folder=self.runtime/'runs'/row['id'];folder.mkdir(parents=True)
  (folder/'case.env').write_text(environment.replace('\n50\n',f'\n{frequency}\n'),encoding='utf-8');(folder/'result.json').write_text(json.dumps(result),encoding='utf-8')
  science.write_manifest(row['id'],plan,folder);self.module.STORE.finish(row['id'],'SUCCEEDED',owner='fixture');return row['id'],folder
 def test_real_compare_route_reads_artifacts_and_verifies_hashes(self):
  left,_=self.create_completed_fixture();right,_=self.create_completed_fixture(100)
  response=self.client.post('/api/jobs/compare',json={'ids':[left,right]});self.assertEqual(response.status_code,200,response.text);result=response.json()
  self.assertTrue(result['comparable']);self.assertEqual(result['pairs'][0]['changed_controlled_variables'],['frequency_hz']);self.assertTrue(result['series'][0]['evidence']['manifest']['result_hash_verified']);self.assertFalse(result['execution_started'])
 def test_different_environment_is_visible_as_not_comparable(self):
  left,_=self.create_completed_fixture();right,_=self.create_completed_fixture(100,ENV.replace('1500','1510'))
  response=self.client.post('/api/jobs/compare',json={'ids':[left,right]});self.assertEqual(response.status_code,200,response.text);self.assertFalse(response.json()['comparable']);self.assertFalse(response.json()['pairs'][0]['checks']['same_environment_input'])
 def test_tampered_result_is_not_compared_as_verified_output(self):
  left,_=self.create_completed_fixture();right,folder=self.create_completed_fixture(100)
  with (folder/'result.json').open(encoding='utf-8') as stream:result=json.load(stream)
  result['title']='altered after manifest';(folder/'result.json').write_text(json.dumps(result),encoding='utf-8')
  response=self.client.post('/api/jobs/compare',json={'ids':[left,right]});self.assertEqual(response.status_code,409);self.assertIn('溯源',response.json()['detail'])
 def test_unfinished_or_invalid_comparison_does_not_run_solver(self):
  pending=self.client.post('/api/jobs',json=PLAN).json()['ids'][0]
  for ids in [[pending,pending],['../config.json','aaaaaaaaaaaa'],['aaaaaaaaaaaa']]:self.assertEqual(self.client.post('/api/jobs/compare',json={'ids':ids}).status_code,422)
  self.assertEqual(self.client.post('/api/jobs/compare',json={'ids':[pending,'aaaaaaaaaaaa']}).status_code,409)

if __name__=='__main__':unittest.main()
