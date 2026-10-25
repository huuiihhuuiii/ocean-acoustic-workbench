"""Run a real Python subprocess against isolated, test-owned research files."""
import asyncio,json,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import research_tasks as research

async def main():
    workspace=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(dir=workspace/'.local') as temp:
        root=Path(temp).resolve();assert root.is_relative_to((workspace/'.local').resolve())
        (root/'.local').mkdir();jobs={};processes={};stop=asyncio.Event()
        def create(identity,plan):jobs[identity]={'id':identity,'plan':plan,'state':'RUNNING'}
        def update(identity,state,error=None):jobs[identity].update(state=state,error=error)
        engine=research.Engine(root,lambda:{},lambda identity:jobs[identity],create,update,processes,threading.RLock(),stop)
        first=await engine.execute('create_research_task',{'title':'Test','objective':'Test objective'})
        assert first['id']==(await engine.execute('create_research_task',{'title':'Test','objective':'Test objective'}))['id']
        identity=first['id'];folder=Path(first['directory'])
        try:await engine.execute('write_research_file',{'id':identity,'file':'../escape.py','content':'x'});raise AssertionError('escape accepted')
        except ValueError:pass
        await engine.execute('write_research_file',{'id':identity,'file':'test.py','content':'raise RuntimeError("fixture failure")'})
        failed=await engine.execute('run_research_script',{'id':identity,'file':'test.py'})
        assert failed['exit_code']!=0 and jobs[identity]['state']=='FAILED'
        await engine.execute('write_research_file',{'id':identity,'file':'test.py','content':'from pathlib import Path\nPath("values.csv").write_text("x,y\\n1,2\\n")'})
        result=await engine.execute('run_research_script',{'id':identity,'file':'test.py'})
        assert result['exit_code']==0 and not processes
        report={'method':'Test method','assumptions':['Test only'],'inputs':['x=1'],'sources':['Analytic fixture'],'outputs':[{'file':'missing.csv'}],'checks':[{'name':'Output identity','passed':True,'evidence':'values.csv has x=1,y=2'}],'conclusion':'Test conclusion','limitations':['Fixture only']}
        try:await engine.execute('finish_research_task',{'id':identity,'report':report});raise AssertionError('missing output accepted')
        except ValueError:pass
        report['outputs']=[{'file':'values.csv','caption':'data'}]
        await engine.execute('finish_research_task',{'id':identity,'report':report})
        assert jobs[identity]['state']=='SUCCEEDED'
        saved=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
        assert saved['outputs'][0]['bytes']>0 and saved['outputs'][0]['sha256']
        assert len(saved['executions'])==2 and saved['executions'][-1]['exit_code']==0
        try:await engine.execute('write_research_file',{'id':identity,'file':'other.py','content':'pass'});raise AssertionError('finished job mutable')
        except ValueError:pass
        assert '$ref' not in json.dumps(research.tools())
    print('PASS: real Python execution, failed-step repair, path guard, idempotent creation, output validation, report hashes and completed-task immutability')
asyncio.run(main())
