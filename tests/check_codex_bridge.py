"""Exercise app-server tool routing and cancellation without provider calls."""
import asyncio,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import codex_bridge as bridge

class Fake:
    instances=[];requests=[]
    async def start(self):self.events=[];self.sent=[];self.closed=False;self.instances.append(self);return self
    async def rpc(self,method,params):
        self.requests.append((method,params))
        if method=='account/read':return {'account':{'type':'chatgpt'}}
        if method in ('thread/start','thread/resume'):
            assert params['sandbox']=='read-only'
            return {'thread':{'id':'thread'}}
        self.events=[{'method':'item/agentMessage/delta','params':{'itemId':'answer','delta':'verified '}},{'id':20,'method':'item/tool/call','params':{'tool':'get_job','arguments':{'id':'abc'}}},{'method':'item/completed','params':{'item':{'type':'agentMessage','id':'answer','text':'verified answer'}}},{'method':'turn/completed','params':{'turn':{'status':'completed'}}}]
        return {'turn':{'id':'turn'}}
    async def send(self,value):self.sent.append(value)
    async def close(self):self.closed=True

async def main():
    with patch.object(bridge,'Server',Fake):
        trace=[];calls=[]
        def execute(name,args):calls.append((name,args));return {'state':'SUCCEEDED','error':None}
        result=await bridge.run([],[],execute,asyncio.Event(),trace,'guide',Path(__file__).resolve().parents[1])
        assert result=='verified answer' and calls==[('get_job',{'id':'abc'})]
        assert Fake.instances[-1].sent[0]['result']['success'] and Fake.instances[-1].closed
        assert trace[0]['status']=='done'
        stop=asyncio.Event();stop.set()
        result=await bridge.run([],[],execute,stop,[],'guide',Path(__file__).resolve().parents[1])
        assert 'Codex' in result and Fake.instances[-1].closed
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);(root/'.local').mkdir();progress={}
        with patch.object(bridge,'Server',Fake):
            await bridge.run([{'role':'user','content':'first'}],[],execute,asyncio.Event(),[],'guide',root,session='one',progress=progress)
            assert bridge.session_thread(root,'one')=='thread' and progress['partial']=='verified answer'
            await bridge.run([{'role':'user','content':'second'}],[],execute,asyncio.Event(),[],'guide',root,session='one')
            assert bridge.session_thread(root,'other') is None
            assert Fake.requests[-2][0]=='thread/resume'
            assert Fake.requests[-1][1]['input'][0]['text']=='second'
    print('PASS: Codex read-only setup, dynamic tool response, answer extraction, cancellation and cleanup')
asyncio.run(main())
