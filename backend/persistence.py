"""SQLite transactions and a durable, single-executor course simulation queue.

Importing this module or constructing JobStore has no filesystem side effects.
Only explicit migrate/startup calls touch the selected database. Every operation
uses its own connection; the process lock prevents two MATLAB workers sharing it.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

SCHEMA_VERSION = 2
ACTIVE = ('QUEUED', 'RUNNING')
TERMINAL = ('SUCCEEDED', 'FAILED', 'CANCELLED', 'INTERRUPTED')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class StoreError(ValueError):
    status = 422


class IdempotencyConflict(StoreError):
    status = 409


class WorkerLock:
    """OS-held lock, automatically released on process exit, including crashes."""
    def __init__(self, path):
        self.path = Path(path)
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open('a+b')
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close(); return False
        self.handle = handle
        return True

    def release(self):
        if not self.handle: return
        self.handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_UN)
        finally:
            self.handle.close(); self.handle = None


class JobStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self, *, immediate=False):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout=15000')
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            if immediate: connection.execute('BEGIN IMMEDIATE')
            with connection:
                yield connection
        finally:
            connection.close()

    def migrate(self):
        """Additive transaction with an online SQLite backup before upgrades."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.is_file() and self.path.stat().st_size > 0
        backup = None
        with self.connection() as connection:
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise StoreError('数据库版本比当前程序更新，请使用匹配程序；没有自动降级。')
            if version == SCHEMA_VERSION: return None
            if existed:
                folder = self.path.parent / 'backups'; folder.mkdir(exist_ok=True)
                backup = folder / f'{self.path.stem}.pre-queue-v2.{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.{uuid.uuid4().hex[:8]}.sqlite3'
                destination = sqlite3.connect(backup)
                try: connection.backup(destination)
                finally: destination.close()
        with self.connection(immediate=True) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,state TEXT,created TEXT,updated TEXT,plan TEXT,error TEXT)')
            connection.execute('CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,session TEXT,role TEXT,text TEXT,created TEXT)')
            job_columns = {row['name'] for row in connection.execute('PRAGMA table_info(jobs)')}
            for column, kind in [('batch_id','TEXT'),('claimed_by','TEXT'),('claimed_at','TEXT')]:
                if column not in job_columns: connection.execute(f'ALTER TABLE jobs ADD COLUMN {column} {kind}')
            if 'metadata' not in {row['name'] for row in connection.execute('PRAGMA table_info(messages)')}:
                connection.execute("ALTER TABLE messages ADD COLUMN metadata TEXT DEFAULT '{}'")
            connection.execute('CREATE TABLE IF NOT EXISTS submissions(batch_id TEXT PRIMARY KEY,scope TEXT NOT NULL,idempotency_key TEXT,plan_sha256 TEXT NOT NULL,ids TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(scope,idempotency_key))')
            connection.execute('CREATE INDEX IF NOT EXISTS jobs_queue_idx ON jobs(state,created)')
            connection.execute('CREATE INDEX IF NOT EXISTS messages_session_idx ON messages(session,id DESC)')
            connection.execute('CREATE INDEX IF NOT EXISTS submissions_plan_idx ON submissions(scope,plan_sha256)')
            connection.execute('CREATE TABLE IF NOT EXISTS job_events(id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,previous_state TEXT,state TEXT NOT NULL,created TEXT NOT NULL,note TEXT)')
            connection.execute('CREATE INDEX IF NOT EXISTS job_events_job_idx ON job_events(job_id,id)')
            connection.execute('CREATE TABLE IF NOT EXISTS queue_settings(id INTEGER PRIMARY KEY CHECK(id=1),paused INTEGER NOT NULL DEFAULT 0)')
            connection.execute('INSERT OR IGNORE INTO queue_settings(id,paused) VALUES(1,0)')
            connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        with self.connection() as connection:
            connection.execute('PRAGMA journal_mode=WAL')
        return str(backup) if backup else None

    @staticmethod
    def _decode(row):
        if row is None: return None
        value = dict(row); value['plan'] = json.loads(value['plan']); return value

    def get(self, job_id):
        with self.connection() as connection:
            return self._decode(connection.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())

    def list(self, limit=100):
        with self.connection() as connection:
            return [self._decode(row) for row in connection.execute('SELECT * FROM jobs ORDER BY julianday(created) DESC,rowid DESC LIMIT ?',(limit,))]

    def submit(self, plan, *, scope='local', idempotency_key=None, cases=None):
        if idempotency_key is not None and not re.fullmatch(r'[A-Za-z0-9_.:-]{8,128}',idempotency_key):
            raise StoreError('幂等标识须为 8–128 位字母、数字或 _ . : -。')
        if not isinstance(scope,str) or not scope or len(scope)>160:
            raise StoreError('无效任务命名空间')
        canonical = json.dumps(plan if cases is None else {'plan':plan,'cases':cases},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        with self.connection(immediate=True) as connection:
            if idempotency_key:
                previous = connection.execute('SELECT * FROM submissions WHERE scope=? AND idempotency_key=?',(scope,idempotency_key)).fetchone()
                if previous:
                    if previous['plan_sha256'] != digest:
                        raise IdempotencyConflict('同一幂等标识已经提交过不同参数，请为新计划生成新的标识。')
                    return {'ids':json.loads(previous['ids']),'batch_id':previous['batch_id'],'reused':True,'plan_sha256':digest}
            # Legacy clients still avoid double-clicks while an identical batch
            # remains active; completed runs can be repeated intentionally.
            previous = connection.execute("SELECT s.* FROM submissions s WHERE s.scope=? AND s.plan_sha256=? AND EXISTS(SELECT 1 FROM jobs j WHERE j.batch_id=s.batch_id AND j.state IN ('QUEUED','RUNNING')) ORDER BY s.created DESC LIMIT 1",(scope,digest)).fetchone()
            if previous and not idempotency_key:
                return {'ids':json.loads(previous['ids']),'batch_id':previous['batch_id'],'reused':True,'plan_sha256':digest}
            batch = uuid.uuid4().hex; ids=[]; created=now()
            expanded=cases if cases is not None else [{**plan,'frequency_hz':frequency,'source_depth_m':depth} for frequency in plan['frequencies_hz'] for depth in plan['source_depths_m']]
            for original in expanded:
                job_id=uuid.uuid4().hex[:12];ids.append(job_id)
                case={**original}
                if cases is not None:case['batch_id']=batch
                connection.execute('INSERT INTO jobs(id,state,created,updated,plan,error,batch_id) VALUES(?,?,?,?,?,NULL,?)',(job_id,'QUEUED',created,created,json.dumps(case,ensure_ascii=False),batch))
                connection.execute('INSERT INTO job_events(job_id,previous_state,state,created,note) VALUES(?,NULL,?,?,?)',(job_id,'QUEUED',created,'参数已校验，等待持久队列领取'))
            connection.execute('INSERT INTO submissions VALUES(?,?,?,?,?,?)',(batch,scope,idempotency_key,digest,json.dumps(ids),created))
            return {'ids':ids,'batch_id':batch,'reused':False,'plan_sha256':digest}

    def paused(self):
        with self.connection() as connection:
            return bool(connection.execute('SELECT paused FROM queue_settings WHERE id=1').fetchone()[0])

    def set_paused(self, value):
        with self.connection(immediate=True) as connection:
            connection.execute('UPDATE queue_settings SET paused=? WHERE id=1',(int(bool(value)),))

    def claim_next(self, owner):
        with self.connection(immediate=True) as connection:
            if connection.execute('SELECT paused FROM queue_settings WHERE id=1').fetchone()[0]: return None
            row=connection.execute("SELECT * FROM jobs WHERE state='QUEUED' ORDER BY julianday(created),rowid LIMIT 1").fetchone()
            if not row: return None
            created=now()
            connection.execute("UPDATE jobs SET state='RUNNING',claimed_by=?,claimed_at=?,updated=? WHERE id=? AND state='QUEUED'",(owner,created,created,row['id']))
            connection.execute('INSERT INTO job_events(job_id,previous_state,state,created,note) VALUES(?,?,?,?,?)',(row['id'],'QUEUED','RUNNING',created,'固定模板执行器领取'))
            result=dict(row);result.update(state='RUNNING',claimed_by=owner,claimed_at=created,updated=created)
            return self._decode(result)

    def finish(self, job_id, state, error=None, *, owner=None):
        if state not in TERMINAL: raise StoreError('无效终态')
        with self.connection(immediate=True) as connection:
            row=connection.execute('SELECT state,claimed_by FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not row: return False
            if row['state'] not in ACTIVE: return False
            if state=='CANCELLED' and row['state']=='RUNNING' and owner is not None and row['claimed_by']!=owner:return False
            if state != 'CANCELLED' and (row['state']!='RUNNING' or (owner is not None and row['claimed_by']!=owner)): return False
            created=now()
            connection.execute('UPDATE jobs SET state=?,error=?,updated=? WHERE id=?',(state,error,created,job_id))
            connection.execute('INSERT INTO job_events(job_id,previous_state,state,created,note) VALUES(?,?,?,?,?)',(job_id,row['state'],state,created,error))
            return True

    def recover_running(self):
        """Call only after exclusive WorkerLock acquisition; queued rows survive."""
        with self.connection(immediate=True) as connection:
            rows=connection.execute("SELECT id FROM jobs WHERE state='RUNNING'").fetchall();created=now()
            for row in rows:
                note='上次执行器已退出，计算被中断；未把已有文件误报为成功，也未自动重跑。请管理员确认无残留 MATLAB 进程后恢复队列。'
                connection.execute("UPDATE jobs SET state='INTERRUPTED',error=?,updated=? WHERE id=?",(note,created,row['id']))
                connection.execute('INSERT INTO job_events(job_id,previous_state,state,created,note) VALUES(?,?,?,?,?)',(row['id'],'RUNNING','INTERRUPTED',created,note))
            if rows:connection.execute('UPDATE queue_settings SET paused=1 WHERE id=1')
            return len(rows)

    def events(self, job_id):
        with self.connection() as connection:
            return [dict(row) for row in connection.execute('SELECT * FROM job_events WHERE job_id=? ORDER BY id',(job_id,))]


def restore_database(database, backup):
    """Explicit operator-only rollback. Stop every service before calling."""
    database,backup=Path(database).resolve(),Path(backup).resolve()
    if database.resolve()==backup.resolve() or not backup.is_file(): raise StoreError('无效备份路径')
    source=sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True)
    target=sqlite3.connect(database)
    try: source.backup(target)
    finally: target.close();source.close()
