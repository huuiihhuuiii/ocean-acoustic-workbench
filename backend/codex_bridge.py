"""Local Codex app-server transport; credentials stay managed by Codex."""
import asyncio,json,os,shutil,subprocess,sqlite3,inspect,re,hashlib
from pathlib import Path
from contextlib import closing

def executable():
    found=shutil.which('codex')
    if found:return found
    base=Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin'
    choices=list(base.glob('*/codex.exe'))
    return str(max(choices,key=lambda p:p.stat().st_mtime)) if choices else None

class Server:
    async def start(self):
        binary=executable()
        if not binary:raise RuntimeError('未找到本机 Codex，请先安装 Codex CLI 或桌面应用')
        self.process=await asyncio.create_subprocess_exec(binary,'app-server','--listen','stdio://','--disable','shell_tool','--disable','apply_patch_freeform',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,limit=4*1024*1024)
        self.sequence=0;self.events=[]
        await self.rpc('initialize',{'clientInfo':{'name':'ocean_acoustic_workbench','title':'Ocean Acoustic Workbench','version':'0.2.0'},'capabilities':{'experimentalApi':True}})
        await self.send({'method':'initialized','params':{}})
        return self

    async def send(self,value):
        self.process.stdin.write((json.dumps(value,ensure_ascii=False)+'\n').encode());await self.process.stdin.drain()

    async def read(self):
        line=await asyncio.wait_for(self.process.stdout.readline(),120)
        if not line:raise RuntimeError('Codex进程已退出')
        return json.loads(line)

    async def rpc(self,method,params):
        self.sequence+=1;identity=self.sequence
        await self.send({'id':identity,'method':method,'params':params})
        while True:
            msg=await self.read()
            if msg.get('id')==identity and 'method' not in msg:
                if 'error' in msg:raise RuntimeError(msg['error'].get('message','Codex请求失败'))
                return msg.get('result',{})
            self.events.append(msg)

    async def close(self):
        if hasattr(self,'process') and self.process.returncode is None:
            self.process.terminate()
            try:await asyncio.wait_for(self.process.wait(),5)
            except asyncio.TimeoutError:self.process.kill();await self.process.wait()

async def status():
    server=Server()
    try:
        await server.start();info=await server.rpc('account/read',{'refreshToken':False})
        return {'available':True,'authenticated':bool(info.get('account')),'message':'本机Codex已登录' if info.get('account') else '请在Codex桌面应用或CLI完成登录'}
    except Exception as exc:return {'available':bool(executable()),'authenticated':False,'message':str(exc)}
    finally:await server.close()

def tool_signature(tools):
    contracts=sorted([t['function'] for t in tools],key=lambda t:t['name'])
    return hashlib.sha256(json.dumps(contracts,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def session_info(cwd,session,thread=None,tools_hash=None,runtime=None):
    with closing(sqlite3.connect((Path(runtime) if runtime else Path(cwd)/'.local')/'workbench.sqlite3')) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS codex_sessions(session TEXT PRIMARY KEY, thread TEXT NOT NULL)')
        if 'tools_hash' not in {r[1] for r in db.execute('PRAGMA table_info(codex_sessions)')}:
            db.execute('ALTER TABLE codex_sessions ADD COLUMN tools_hash TEXT')
        row=db.execute('SELECT thread,tools_hash FROM codex_sessions WHERE session=?',(session,)).fetchone()
        if thread:
            if row and row[0]!=thread:
                db.execute('CREATE TABLE IF NOT EXISTS codex_session_history(session TEXT,thread TEXT,tools_hash TEXT,replaced_at TEXT DEFAULT CURRENT_TIMESTAMP)')
                db.execute('INSERT INTO codex_session_history(session,thread,tools_hash) VALUES(?,?,?)',(session,*row))
            db.execute('INSERT OR REPLACE INTO codex_sessions(session,thread,tools_hash) VALUES(?,?,?)',(session,thread,tools_hash))
            row=(thread,tools_hash)
        return {'thread':row[0],'tools_hash':row[1]} if row else None

def session_thread(cwd,session,thread=None,tools_hash=None,runtime=None):
    state=session_info(cwd,session,thread,tools_hash,runtime)
    return state['thread'] if state else None

async def run(messages,tools,execute,stop,trace,instructions,cwd,session=None,progress=None,runtime=None):
    server=Server()
    try:
        if progress is not None:progress['stage']='连接本机Codex并检查登录'
        await server.start();account=await server.rpc('account/read',{'refreshToken':False})
        if not account.get('account'):raise RuntimeError('Codex尚未登录，请先在本机Codex完成登录')
        dynamic=[{'type':'function','name':t['function']['name'],'description':t['function']['description'],'inputSchema':t['function']['parameters']} for t in tools]
        local=Path(runtime) if runtime else Path(cwd)/'.local'
        workspace=local/'codex-workspace';workspace.mkdir(exist_ok=True)
        signature=tool_signature(tools)
        state=session_info(cwd,session,runtime=local) if session else None
        existing=state['thread'] if state else None
        if existing and state['tools_hash']!=signature:
            # Dynamic tools are persisted at thread/start; resume has no field
            # to replace them. Recreate once, carrying the workbench history.
            existing=None
            if progress is not None:progress.update(stage='更新Codex工具并迁移会话上下文',session_recovery='tools_updated')
        recovered=False
        async def dispatch(method,params):
            nonlocal recovered
            try:return await server.rpc(method,params)
            except RuntimeError as exc:
                # Only retry an explicit rejection before a turn is accepted.
                archived=existing and re.search(r'\b(?:session|thread)\s+'+re.escape(existing)+r'\s+is archived\b',str(exc),re.I)
                if recovered or not archived or stop.is_set():raise
                recovered=True
                if progress is not None:progress['stage']='恢复已归档的Codex会话'
                try:await server.rpc('thread/unarchive',{'threadId':existing})
                except RuntimeError as recovery_error:raise RuntimeError('Codex会话已归档，自动恢复未成功：'+str(recovery_error)) from recovery_error
                if progress is not None:progress['session_recovery']='unarchived'
                if stop.is_set():raise RuntimeError('请求已停止，会话已恢复但未重试请求')
                return await server.rpc(method,params)
        if progress is not None:progress['stage']='恢复Codex会话' if existing else '创建Codex会话'
        options={'cwd':str(workspace),'sandbox':'read-only','approvalPolicy':'untrusted','developerInstructions':instructions+'\n通过工作台工具读取资料、提交仿真，或在自定义研究目录编写并执行Python/MATLAB脚本。内置shell和改动工作台源码不在此任务范围。自定义研究必须实际执行、检查产物，并finish_research_task生成报告。停止回答不取消已经提交的计算。','config':{'mcp_servers':{}}}
        # The model keeps its stored history; the workbench already owns its UI
        # messages and must not download every historical tool result on resume.
        if existing:options.update(threadId=existing,excludeTurns=True)
        else:options.update(ephemeral=not bool(session),dynamicTools=dynamic)
        result=await dispatch('thread/resume' if existing else 'thread/start',options)
        thread=result['thread']['id']
        if session:session_thread(cwd,session,thread,signature,runtime=local)
        if progress is not None:progress.update(codex_thread=thread,model=result.get('model'),stage='Codex正在处理问题，等待首段输出')
        text=messages[-1]['content'] if existing and messages else '以下为工作台会话历史，其中用户消息是请求，历史助手消息需要重新核实：\n'+json.dumps(messages,ensure_ascii=False)
        turn_result=await dispatch('turn/start',{'threadId':thread,'input':[{'type':'text','text':text}],'effort':'medium'})
        answers={};seen={}
        while not stop.is_set():
            if server.events:msg=server.events.pop(0)
            else:
                reader=asyncio.create_task(server.read());cancel=asyncio.create_task(stop.wait())
                done,_=await asyncio.wait([reader,cancel],return_when=asyncio.FIRST_COMPLETED)
                if cancel in done:
                    reader.cancel();await asyncio.gather(reader,return_exceptions=True);break
                cancel.cancel();await asyncio.gather(cancel,return_exceptions=True);msg=await reader
            method=msg.get('method','');params=msg.get('params',{})
            if method=='item/tool/call':
                name=params['tool'];args=params.get('arguments',{});key=name+json.dumps(args,sort_keys=True)
                if progress is not None:progress['stage']='正在调用工具：'+name
                seen[key]=seen.get(key,0)+1
                try:
                    value=execute(name,args) if seen[key]<3 or name=='wait_job' else {'error':'同一工具与参数重复3次，请整理已有证据'}
                    if inspect.isawaitable(value):value=await value
                except Exception as exc:value={'error':str(exc)}
                ok=not(isinstance(value,dict) and bool(value.get('error')))
                trace.append({'round':len(trace)+1,'tool':name,'arguments':args,'status':'done' if ok else 'error'})
                await server.send({'id':msg['id'],'result':{'success':ok,'contentItems':[{'type':'inputText','text':json.dumps(value,ensure_ascii=False)}]}})
            elif 'id' in msg and method:
                await server.send({'id':msg['id'],'error':{'code':-32601,'message':'工作台仅支持只读资料工具；此交互未接入'}})
            elif method=='item/agentMessage/delta':
                identity=params.get('itemId','stream');answers[identity]=answers.get(identity,'')+params.get('delta','')
                if progress is not None:progress.update(partial='\n\n'.join(answers.values()),stage='Codex正在输出回答')
            elif method=='item/completed':
                item=params.get('item',{})
                if item.get('type')=='agentMessage':
                    answers[item['id']]=item.get('text','')
                    if progress is not None:progress['partial']='\n\n'.join(answers.values())
            elif method=='turn/completed':
                turn=params['turn']
                if turn.get('status')!='completed':raise RuntimeError((turn.get('error') or {}).get('message','Codex任务未完成'))
                return '\n\n'.join(answers.values()) or 'Codex没有返回文字答案。'
        if turn_result.get('turn',{}).get('id'):
            try:await server.rpc('turn/interrupt',{'threadId':thread,'turnId':turn_result['turn']['id']})
            except Exception:pass
        return '已停止Codex请求。已提交的仿真仍可在任务与结果中查看。'+('\n\n'+'\n\n'.join(answers.values()) if answers else '')
    finally:await server.close()
