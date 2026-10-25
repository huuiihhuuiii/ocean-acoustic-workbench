"""Resume cannot install dynamic tools: migrate only when the contract changes."""
import asyncio
from pathlib import Path
import sys
import tempfile
import sqlite3
from contextlib import closing
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import codex_bridge as bridge

TOOL = {'type': 'function', 'function': {'name': 'list_research_skills', 'description': 'List skills', 'parameters': {'type': 'object', 'properties': {}}}}


class Server:
    threads = {}
    calls = []
    async def start(self):
        self.events = []
        return self
    async def rpc(self, method, params):
        self.calls.append((method, params))
        if method == 'account/read':return {'account': {'type': 'chatgpt'}}
        if method == 'thread/start':
            thread = 'thread-' + str(len(self.threads)+1)
            self.threads[thread] = params['dynamicTools']
            return {'thread': {'id': thread}}
        if method == 'thread/resume':
            assert 'dynamicTools' not in params, 'Resume does not accept dynamicTools'
            return {'thread': {'id': params['threadId']}}
        if method == 'turn/start':
            available = any(t['name'] == 'list_research_skills' for t in self.threads[params['threadId']])
            self.events = ([{'id': 100, 'method': 'item/tool/call', 'params': {'tool': 'list_research_skills', 'arguments': {}}}] if available else []) + [{'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'id': 'answer', 'text': 'skills available' if available else 'skills missing'}}}, {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}}]
            return {'turn': {'id': 'turn'}}
        raise AssertionError(method)
    async def send(self, value):pass
    async def close(self):pass


async def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp);(root/'.local').mkdir()
        executed = []
        def execute(name, args):executed.append(name);return {'skills': ['at-ram']}
        with patch.object(bridge, 'Server', Server):
            await bridge.run([{'role': 'user', 'content': 'old question'}], [], execute, asyncio.Event(), [], 'guide', root, session='chat')
            old = bridge.session_thread(root, 'chat')
            progress = {}
            reply = await bridge.run([{'role': 'user', 'content': 'run RAM skill'}], [TOOL], execute, asyncio.Event(), [], 'guide', root, session='chat', progress=progress)
            assert reply == 'skills available' and executed == ['list_research_skills']
            assert bridge.session_thread(root, 'chat') != old and old in Server.threads
            assert 'run RAM skill' in Server.calls[-1][1]['input'][0]['text']
            assert progress['session_recovery'] == 'tools_updated'
            with closing(sqlite3.connect(root/'.local/workbench.sqlite3')) as db:
                assert db.execute('SELECT thread FROM codex_session_history WHERE session=?',('chat',)).fetchone()[0] == old
            count = len(Server.threads)
            await bridge.run([{'role': 'user', 'content': 'continue'}], [TOOL], execute, asyncio.Event(), [], 'guide', root, session='chat')
            assert len(Server.threads) == count and Server.calls[-2][0] == 'thread/resume'
            # Legacy mappings have no fingerprint and must be migrated once.
            bridge.session_thread(root, 'legacy', old)
            await bridge.run([{'role': 'user', 'content': 'legacy RAM'}], [TOOL], execute, asyncio.Event(), [], 'guide', root, session='legacy')
            assert bridge.session_thread(root, 'legacy') != old
    print('PASS: tool upgrade and legacy migration; history preserved, current tool callable, stable contracts resume')


asyncio.run(main())
