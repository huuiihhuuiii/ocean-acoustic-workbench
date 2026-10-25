"""Exercise the real RPC/StreamReader boundary with an oversized resume history."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import codex_bridge as bridge


class HistoryServer(bridge.Server):
    last = None

    async def start(self):
        self.process = SimpleNamespace(stdout=asyncio.StreamReader(limit=4*1024*1024))
        self.sequence = 0
        self.events = []
        self.calls = []
        self.closed = False
        HistoryServer.last = self
        return self

    async def send(self, request):
        method, params = request['method'], request['params']
        self.calls.append((method, params))
        if method == 'account/read':
            result = {'account': {'type': 'chatgpt'}}
        elif method == 'thread/resume':
            result = {'thread': {'id': 'existing-thread'}}
            if not params.get('excludeTurns'):
                result['thread']['turns'] = ['history' * 800000]
        elif method == 'turn/start':
            result = {'turn': {'id': 'one-turn'}}
        else:
            raise AssertionError(method)
        self.process.stdout.feed_data((json.dumps({'id': request['id'], 'result': result}) + '\n').encode())
        if method == 'turn/start':
            for event in [{'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'id': 'answer', 'text': 'confirmed'}}}, {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}}]:
                self.process.stdout.feed_data((json.dumps(event) + '\n').encode())

    async def close(self):
        self.closed = True


async def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / '.local').mkdir()
        bridge.session_thread(root, 'chat', 'existing-thread', bridge.tool_signature([]))
        with patch.object(bridge, 'Server', HistoryServer):
            result = await bridge.run([{'role': 'user', 'content': 'latest question'}], [], lambda *a: None, asyncio.Event(), [], 'guide', root, session='chat')
        assert result == 'confirmed' and HistoryServer.last.closed
        calls = HistoryServer.last.calls
        assert sum(method == 'turn/start' for method, _ in calls) == 1
        assert next(params for method, params in calls if method == 'thread/resume')['excludeTurns'] is True
        assert bridge.session_thread(root, 'chat') == 'existing-thread'
    print('PASS: oversized historical payload avoided at real RPC reader; same thread, one new turn')


asyncio.run(main())
