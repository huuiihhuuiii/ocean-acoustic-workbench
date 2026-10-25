"""Temporary SQLite only: migration, concurrency, queue and replay semantics."""
import concurrent.futures
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from persistence import JobStore,WorkerLock,IdempotencyConflict,StoreError,restore_database

PLAN={'template':'munk_5000m','frequencies_hz':[50,100],'source_depths_m':[500,1000],'receiver_depth_m':1000,'range_min_km':1,'range_max_km':10,'range_points':101,'depth_points':101}

class Persistence(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.path=Path(self.directory.name)/'jobs.sqlite3';self.store=JobStore(self.path);self.store.migrate()
 def tearDown(self):self.directory.cleanup()
 def test_legacy_upgrade_backups_and_preserves_records_and_is_reversible(self):
  path=Path(self.directory.name)/'legacy.sqlite3'
  with closing(sqlite3.connect(path)) as connection:
   connection.executescript('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT,created TEXT,updated TEXT,plan TEXT,error TEXT);CREATE TABLE messages(id INTEGER PRIMARY KEY,session TEXT,role TEXT,text TEXT,created TEXT);')
   connection.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',('abc','SUCCEEDED','t','t',json.dumps(PLAN),None));connection.execute('INSERT INTO messages VALUES(1,?,?,?,?)',('old','assistant','历史回答','t'));connection.commit()
  legacy=JobStore(path);backup=legacy.migrate();self.assertTrue(Path(backup).is_file());self.assertEqual(legacy.get('abc')['state'],'SUCCEEDED')
  with legacy.connection() as connection:
   self.assertEqual(connection.execute('SELECT text FROM messages').fetchone()[0],'历史回答');self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],2)
  self.assertIsNone(legacy.migrate());restore_database(path,backup)
  with closing(sqlite3.connect(path)) as connection:
   self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],0);self.assertNotIn('batch_id',{row[1] for row in connection.execute('PRAGMA table_info(jobs)')});self.assertEqual(connection.execute('SELECT state FROM jobs').fetchone()[0],'SUCCEEDED')
 def test_connections_close_and_failed_transaction_rolls_back(self):
  with self.assertRaises(RuntimeError):
   with self.store.connection(immediate=True) as connection:
    connection.execute("INSERT INTO messages(session,role,text) VALUES('test','user','rollback')");raise RuntimeError('test rollback')
  with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
  with self.store.connection() as check:self.assertEqual(check.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
 def test_same_idempotency_key_replays_even_after_completion(self):
  first=self.store.submit(PLAN,idempotency_key='request-0001');again=self.store.submit(PLAN,idempotency_key='request-0001')
  self.assertEqual(first['ids'],again['ids']);self.assertTrue(again['reused'])
  while job:=self.store.claim_next('owner'):self.store.finish(job['id'],'SUCCEEDED',owner='owner')
  self.assertEqual(first['ids'],self.store.submit(PLAN,idempotency_key='request-0001')['ids'])
  with self.assertRaises(IdempotencyConflict):self.store.submit({**PLAN,'receiver_depth_m':900},idempotency_key='request-0001')
 def test_idempotency_namespace_isolates_visitors(self):
  a=self.store.submit(PLAN,scope='visitor-a',idempotency_key='request-0001');b=self.store.submit(PLAN,scope='visitor-b',idempotency_key='request-0001')
  self.assertNotEqual(a['ids'],b['ids']);self.assertEqual(len(self.store.list()),8)
 def test_legacy_identical_active_batch_is_reused_but_finished_can_repeat(self):
  a=self.store.submit(PLAN);self.assertEqual(a['ids'],self.store.submit(PLAN)['ids'])
  for job_id in a['ids']:self.store.finish(job_id,'CANCELLED')
  self.assertNotEqual(a['ids'],self.store.submit(PLAN)['ids'])
 def test_concurrent_same_request_creates_one_atomic_batch(self):
  with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:results=list(pool.map(lambda _:self.store.submit(PLAN,idempotency_key='request-race'),range(20)))
  self.assertEqual(len({tuple(item['ids']) for item in results}),1);self.assertEqual(len(self.store.list()),4);self.assertEqual(sum(not item['reused'] for item in results),1)
 def test_concurrent_claims_do_not_duplicate_or_drop_tasks(self):
  ids=self.store.submit(PLAN)['ids']
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda owner:self.store.claim_next(owner),[f'owner-{i}' for i in range(12)]))
  self.assertCountEqual([job['id'] for job in results if job],ids);self.assertTrue(all(job['state']=='RUNNING' for job in self.store.list()))
 def test_restart_preserves_queued_and_marks_running_interrupted_and_pauses(self):
  ids=self.store.submit(PLAN)['ids'];running=self.store.claim_next('old-process')
  restarted=JobStore(self.path);self.assertIsNone(restarted.migrate());self.assertEqual(restarted.recover_running(),1)
  self.assertEqual(restarted.get(running['id'])['state'],'INTERRUPTED');self.assertEqual(sum(job['state']=='QUEUED' for job in restarted.list()),3)
  self.assertTrue(restarted.paused());self.assertIsNone(restarted.claim_next('new-process'))
  restarted.set_paused(False);self.assertIn(restarted.claim_next('new-process')['id'],ids);self.assertEqual(restarted.recover_running(),1)
 def test_cancellation_wins_over_late_success_and_owner_is_checked(self):
  self.store.submit(PLAN);job=self.store.claim_next('owner')
  self.assertFalse(self.store.finish(job['id'],'SUCCEEDED',owner='wrong-owner'))
  self.assertTrue(self.store.finish(job['id'],'CANCELLED'));self.assertFalse(self.store.finish(job['id'],'SUCCEEDED',owner='owner'))
  self.assertEqual(self.store.get(job['id'])['state'],'CANCELLED');self.assertEqual([event['state'] for event in self.store.events(job['id'])],['QUEUED','RUNNING','CANCELLED'])
 def test_pause_survives_reopening_database(self):
  self.store.submit(PLAN);self.store.set_paused(True);self.assertTrue(JobStore(self.path).paused());self.assertIsNone(self.store.claim_next('owner'))
 def test_os_worker_lock_excludes_a_second_executor_and_can_release(self):
  a=WorkerLock(self.path.with_suffix('.lock'));b=WorkerLock(self.path.with_suffix('.lock'))
  try:self.assertTrue(a.acquire());self.assertFalse(b.acquire());a.release();self.assertTrue(b.acquire())
  finally:a.release();b.release()
 def test_constructing_store_has_no_filesystem_side_effect(self):
  path=Path(self.directory.name)/'not-created'/'db.sqlite3';JobStore(path);self.assertFalse(path.parent.exists())
 def test_future_schema_rejected_without_downgrade(self):
  with self.store.connection() as connection:connection.execute('PRAGMA user_version=99')
  with self.assertRaises(StoreError):self.store.migrate()
  with self.store.connection() as connection:self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],99)

if __name__=='__main__':unittest.main()
