"""Archived sessions must recover before dispatch, without replaying completed turns."""
import asyncio
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import codex_bridge as bridge

THREAD = '01a13f7a-a264-7253-a7d6-a88de8fe47fa'


class ArchivedServer:
    fail_method = 'thread/resume'
    unrelated = False
    persistent_failure = False
    last = None

    async def start(self):
        self.events = []
        self.calls = []
        self.archived = True
        self.turns = 0
        self.closed = False
        ArchivedServer.last = self
        return self

    async def rpc(self, method, params):
        self.calls.append((method, params))
        if method == 'account/read':
            return {'account': {'type': 'chatgpt'}}
        if method == self.fail_method and (self.archived or self.persistent_failure):
            raise RuntimeError('network unavailable' if self.unrelated else f'session {THREAD} is archived. Run `codex unarchive {THREAD}` to unarchive it first.')
        if method == 'thread/unarchive':
            assert params == {'threadId': THREAD}
            self.archived = False
            return {'thread': {'id': THREAD}}
        if method == 'thread/resume':
            return {'thread': {'id': THREAD}}
        if method == 'turn/start':
            self.turns += 1
            self.events = [{'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'id': 'answer', 'text': 'restored'}}}, {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}}]
            return {'turn': {'id': 'turn'}}
        raise AssertionError('Unexpected RPC: ' + method)

    async def close(self):
        self.closed = True


async def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / '.local').mkdir()
        bridge.session_thread(root, 'workbench', THREAD, bridge.tool_signature([]))
        for method in ['thread/resume', 'turn/start']:
            ArchivedServer.fail_method = method
            progress = {}
            with patch.object(bridge, 'Server', ArchivedServer):
                reply = await bridge.run([{'role': 'user', 'content': 'continue'}], [], lambda *a: None, asyncio.Event(), [], 'guide', root, session='workbench', progress=progress)
            server = ArchivedServer.last
            assert reply == 'restored' and server.closed and server.turns == 1
            assert sum(m == 'thread/unarchive' for m, _ in server.calls) == 1
            assert not any(m == 'thread/start' for m, _ in server.calls)
            assert bridge.session_thread(root, 'workbench') == THREAD
            assert progress['session_recovery'] == 'unarchived'
        ArchivedServer.unrelated = True
        ArchivedServer.fail_method = 'thread/resume'
        with patch.object(bridge, 'Server', ArchivedServer):
            try:
                await bridge.run([], [], lambda *a: None, asyncio.Event(), [], 'guide', root, session='workbench')
                raise AssertionError('Unrelated error swallowed')
            except RuntimeError as exc:
                assert str(exc) == 'network unavailable'
        assert not any(m == 'thread/unarchive' for m, _ in ArchivedServer.last.calls)
        assert ArchivedServer.last.closed
        ArchivedServer.unrelated = False
        ArchivedServer.persistent_failure = True
        with patch.object(bridge, 'Server', ArchivedServer):
            try:
                await bridge.run([], [], lambda *a: None, asyncio.Event(), [], 'guide', root, session='workbench')
                raise AssertionError('Persistent archive failure swallowed')
            except RuntimeError as exc:
                assert 'is archived' in str(exc)
        assert sum(m == 'thread/unarchive' for m, _ in ArchivedServer.last.calls) == 1
        assert ArchivedServer.last.turns == 0 and ArchivedServer.last.closed
    print('PASS: archived resume and pre-dispatch recovery; one accepted turn, same history, unrelated errors preserved')


asyncio.run(main())
