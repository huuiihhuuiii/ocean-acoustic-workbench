"""ACP lifecycle and real loopback MCP routing; no provider calls."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import dsh_bridge as bridge


class FakePeer:
    instances = []
    async def start(self, cwd):
        self.calls = []; self.closed = False; self.instances.append(self)
    async def rpc(self, method, params, timeout=None):
        self.calls.append((method, params))
        if method in ('session/new', 'session/resume'):
            return {'sessionId': 'persisted-agent', 'configOptions': []}
        if method == 'session/prompt':
            self.on_update({'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': '已核对结果'}}})
            return {'stopReason': 'end_turn'}
        return {}
    async def send(self, message): self.calls.append(('send', message))
    async def close(self): self.closed = True


class RecoverPeer(FakePeer):
    async def rpc(self, method, params, timeout=None):
        if method == 'session/prompt' and not any(m == method for m, _ in self.calls):
            self.calls.append((method, params))
            raise RuntimeError('Internal error: turn failed: DeepSeek Messages stream: tool input is invalid JSON')
        return await super().rpc(method, params, timeout)


class BrokenPeer(FakePeer):
    async def rpc(self, method, params, timeout=None):
        if method == 'session/prompt':
            self.calls.append((method, params)); raise RuntimeError('transport disconnected')
        return await super().rpc(method, params, timeout)


class WaitingPeer(FakePeer):
    async def rpc(self, method, params, timeout=None):
        if method == 'session/prompt':
            self.waiting = asyncio.Event(); await self.waiting.wait(); return {'stopReason': 'cancelled'}
        return await super().rpc(method, params, timeout)
    async def send(self, message):
        await super().send(message)
        if message['method'] == 'session/cancel': self.waiting.set()


async def post(url, value, path=None):
    from urllib.parse import urlsplit
    u = urlsplit(url); reader, writer = await asyncio.open_connection(u.hostname, u.port)
    data = json.dumps(value).encode()
    writer.write(f'POST {path or u.path} HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: {len(data)}\r\n\r\n'.encode() + data)
    await writer.drain(); response = await reader.read(); writer.close(); await writer.wait_closed()
    head, body = response.split(b'\r\n\r\n', 1)
    return head.split(b' ')[1], json.loads(body) if body else None


async def main():
    stop = asyncio.Event(); trace = []; calls = []
    tools = [{'function': {'name': 'get_job', 'description': 'Read task', 'parameters': {'type': 'object'}}}]
    async def execute(name, args): calls.append((name, args)); return {'state': 'SUCCEEDED'}
    mcp = bridge.WorkbenchMCP(tools, execute, stop, trace, {})
    url = await mcp.start()
    try:
        status, result = await post(url, {'id': 1, 'method': 'tools/list'})
        assert status == b'200' and result['result']['tools'][0]['name'] == 'get_job'
        _, result = await post(url, {'id': 2, 'method': 'tools/call', 'params': {'name': 'get_job', 'arguments': {'id': 'abc'}}})
        assert not result['result']['isError'] and calls == [('get_job', {'id': 'abc'})]
        assert trace[0]['status'] == 'done'
        assert (await post(url, {'id': 3, 'method': 'tools/list'}, '/wrong'))[0] == b'404'
        _, result = await post(url, {'id': 4, 'method': 'tools/call', 'params': {'name': 'shell'}})
        assert 'error' in result and len(calls) == 1
        stop.set()
        _, result = await post(url, {'id': 5, 'method': 'tools/call', 'params': {'name': 'get_job'}})
        assert 'error' in result and len(calls) == 1
    finally: await mcp.close()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); (root / '.local').mkdir(); progress = {}
        with patch.object(bridge, 'Peer', FakePeer):
            for text in ('first', 'followup'):
                reply = await bridge.run([{'role': 'user', 'content': text}], tools, execute,
                                         asyncio.Event(), [], 'guide', root, session='chat', progress=progress)
                assert reply == '已核对结果' and FakePeer.instances[-1].closed
            assert FakePeer.instances[0].calls[0][0] == 'session/new'
            assert FakePeer.instances[1].calls[0][0] == 'session/resume'
            assert bridge.saved_session(root, 'chat') == 'persisted-agent'
            assert progress['partial'] == '已核对结果'
            stop = asyncio.Event(); stop.set()
            count = len(FakePeer.instances)
            reply = await bridge.run([], tools, execute, stop, [], 'guide', root)
            assert '已停止' in reply and len(FakePeer.instances) == count
        with patch.object(bridge, 'Peer', RecoverPeer):
            progress = {}
            reply = await bridge.run([], tools, execute, asyncio.Event(), [], 'guide', root, progress=progress)
            assert reply == '已核对结果' and progress['dsh_recovery'] == 'invalid_tool_json'
            prompts = [p for m, p in FakePeer.instances[-1].calls if m == 'session/prompt']
            assert len(prompts) == 2 and '不要重放' in prompts[-1]['prompt'][0]['text']
        with patch.object(bridge, 'Peer', BrokenPeer):
            try: await bridge.run([], tools, execute, asyncio.Event(), [], 'guide', root)
            except RuntimeError as exc: assert str(exc) == 'transport disconnected'
            else: raise AssertionError('transport failure was swallowed')
            assert len([1 for m, p in FakePeer.instances[-1].calls if m == 'session/prompt']) == 1
            assert FakePeer.instances[-1].closed
        with patch.object(bridge, 'Peer', WaitingPeer):
            stop = asyncio.Event(); asyncio.get_running_loop().call_later(.05, stop.set)
            reply = await bridge.run([], tools, execute, stop, [], 'guide', root)
            assert '已停止' in reply and FakePeer.instances[-1].closed
            assert any(m == 'send' and p['method'] == 'session/cancel' for m, p in FakePeer.instances[-1].calls)
    print('PASS: DSH MCP routing, authorization, persistence, resume, active stop, bounded JSON recovery, no transport replay and cleanup')

asyncio.run(main())
