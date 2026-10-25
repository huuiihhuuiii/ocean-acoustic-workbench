import React,{useEffect,useRef,useState} from 'react';
import {Waves,ArrowUp,BookOpen,Download,Trash2,Undo2,Copy,Loader2,Square,Settings2,FlaskConical} from 'lucide-react';
import ChatMessage from './ChatMessage';
import ModelSkillPicker from './ModelSkillPicker';
import QuestionSuggestions from './QuestionSuggestions';
import {serializeChat} from './chatExport';
import './dialogue-workbench.css';

async function api(path,body){
 const response=await fetch('/api/research/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
 const value=await response.json();if(!response.ok)throw Error(typeof value.detail==='string'?value.detail:'请求失败，请检查服务连接');return value;
}
const labels={dsh:'DSH',codex:'Codex',api:'模型接口'};
export default function DialogueWorkbench({draft,notify=()=>{},openSettings}){
 const [session,setSession]=useState(()=>{let value=localStorage.getItem('ocean-research-v07-session');if(!value){value=crypto.randomUUID();localStorage.setItem('ocean-research-v07-session',value)}return value});
 const [previous,setPrevious]=useState(()=>localStorage.getItem('ocean-research-v07-previous')||'');
 const [backend,setBackend]=useState(()=>localStorage.getItem('ocean-research-v07-backend')||'dsh');
 const [rounds,setRounds]=useState(()=>localStorage.getItem('ocean-research-v07-rounds')||'0');
 const [text,setText]=useState(''),[messages,setMessages]=useState([]),[run,setRun]=useState(null),[loading,setLoading]=useState(true),[submitting,setSubmitting]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState(null),[format,setFormat]=useState('md'),[cap,setCap]=useState(null);
 const lastDraft=useRef(null),scroll=useRef(null),follow=useRef(true),sending=useRef(false);
 const busy=submitting||run?.state==='running';
 function chooseBackend(value){setBackend(value);localStorage.setItem('ocean-research-v07-backend',value)}
 useEffect(()=>{let alive=true;setLoading(true);setRun(null);setMessages([]);setError('');
  Promise.all([api('history?session='+encodeURIComponent(session)),api('active?session='+encodeURIComponent(session)),api('capabilities')]).then(([rows,current,capabilities])=>{if(!alive)return;setMessages(rows);setRun(current);setCap(capabilities);if(current?.state==='running'&&current.backend)chooseBackend(current.backend)}).catch(e=>{if(alive)setError(e.message)}).finally(()=>{if(alive)setLoading(false)});return()=>{alive=false}
 },[session]);
 useEffect(()=>{let alive=true;setStatus(null);if(backend!=='api')api(backend+'/status').then(value=>{if(alive)setStatus(value)}).catch(e=>{if(alive)setStatus({message:e.message})});return()=>{alive=false}},[backend]);
 useEffect(()=>{if(draft&&draft.id!==lastDraft.current){lastDraft.current=draft.id;setText(draft.text);follow.current=true}},[draft]);
 useEffect(()=>{if(run?.state!=='running')return;let alive=true,pending=false;
  const poll=async()=>{if(pending)return;pending=true;try{const current=await api('runs/'+run.id);if(!alive)return;setRun(current);if(current.state!=='running'){const rows=await api('history?session='+encodeURIComponent(session));if(alive){setMessages(rows);setError(current.error||'')}}}catch(e){if(alive)setError('连接暂时中断，将继续重连：'+e.message)}finally{pending=false}};
  const timer=setInterval(poll,1000);poll();return()=>{alive=false;clearInterval(timer)}
 },[run?.id,run?.state,session]);
 useEffect(()=>{if(!scroll.current||!follow.current)return;if(!messages.length&&!run?.partial)return;scroll.current.scrollTop=scroll.current.scrollHeight},[messages,run?.partial]);
 async function send(){if(sending.current||busy||loading||!text.trim())return;
  if(backend==='api'&&(!Number.isInteger(Number(rounds))||Number(rounds)<0||Number(rounds)>1000||rounds==='')){setError('工具轮数请填 0–1000 的整数，0 为不限');return}
  sending.current=true;setSubmitting(true);setError('');follow.current=true;
  const message=text;
  try{const result=await api('chat',{session,request_id:crypto.randomUUID(),message,backend,rounds:backend==='api'?Number(rounds):0});setRun({id:result.id,state:'running',backend,stage:'准备请求',trace:[]});setMessages(rows=>[...rows,{role:'user',text:message}]);setText('');localStorage.removeItem('ocean-research-v07-previous');setPrevious('')}
  catch(e){setError(e.message)}finally{sending.current=false;setSubmitting(false)}
 }
 async function stop(){try{await api('runs/'+run.id+'/stop',{});notify('正在停止 Agent；已启动的计算可在任务页取消')}catch(e){setError(e.message)}}
 function switchSession(next){localStorage.setItem('ocean-research-v07-session',next);setSession(next)}
 function clear(){if(busy||loading||!messages.length)return;localStorage.setItem('ocean-research-v07-previous',session);setPrevious(session);switchSession(crypto.randomUUID())}
 function undo(){if(!previous||busy)return;const target=previous;setPrevious('');localStorage.removeItem('ocean-research-v07-previous');switchSession(target)}
 function exportChat(){const mime=format==='json'?'application/json':format==='md'?'text/markdown':'text/plain';const url=URL.createObjectURL(new Blob(['\ufeff',serializeChat(messages,format)],{type:mime+';charset=utf-8'}));const anchor=document.createElement('a');anchor.href=url;anchor.download='海洋声学对话-'+new Date().toISOString().replace(/[:.]/g,'-')+'.'+format;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 async function copy(text){try{await navigator.clipboard.writeText(text);notify('消息已复制')}catch{notify('复制失败，请手动选择文字复制')}}
 return <div className="dialogue-workbench">
  <div className="dialogue-title"><div><span className="eyebrow">RESEARCH AGENT</span><h1>对话工作台</h1><p>围绕研究目标，加载技能、查阅资料、执行计算并核验结果。</p></div><span className="tag">Agent · 研究与执行</span></div>
  <div className="dialogue-layout"><section className="panel dialogue-panel" aria-label="对话工作台">
   <div className="dialogue-toolbar"><label>对话后端 <select aria-label="对话后端" disabled={busy} value={backend} onChange={e=>chooseBackend(e.target.value)}><option value="dsh">DSH · 完整 Agent</option><option value="codex">Codex · 本机 Agent</option><option value="api">现有模型接口</option></select></label><span role="status">{backend==='api'?(cap?.api_configured?'模型接口已配置':'请先配置模型 API Key'):status?.message||'正在检查本机 Agent…'}</span></div>
   {backend==='api'&&<div className="dialogue-toolbar"><label>工具轮数 <input aria-label="Agent工具轮数" type="number" min="0" max="1000" disabled={busy} value={rounds} onChange={e=>{setRounds(e.target.value);localStorage.setItem('ocean-research-v07-rounds',e.target.value)}}/></label><span>0 为不限；达到上限后汇总已有结果</span></div>}
   <div className="dialogue-toolbar"><span>{loading?'载入聊天…':`${messages.length} 条消息`}</span><div className="dialogue-actions"><select aria-label="聊天导出格式" value={format} onChange={e=>setFormat(e.target.value)}><option value="md">Markdown</option><option value="txt">TXT</option><option value="json">JSON</option></select><button className="button" disabled={busy||loading||!messages.length} onClick={exportChat}><Download size={14}/>导出聊天</button><button className="button" disabled={busy||loading||!messages.length} onClick={clear}><Trash2 size={14}/>清空聊天</button>{previous&&<button className="button" disabled={busy||loading} onClick={undo}><Undo2 size={14}/>撤销清空</button>}</div></div>
   <ModelSkillPicker disabled={busy} onSelect={setText}/>
   <div className="dialogue-messages" role="log" aria-label="聊天记录" ref={scroll} onScroll={e=>{const el=e.currentTarget;follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<100}}>
    {!loading&&!messages.length&&<div className="dialogue-welcome"><Waves size={36}/><h2>从一个声学问题开始</h2><p>让资料、方法、实际计算和验证结果连在一起。</p><QuestionSuggestions mode="agent" onSelect={setText}/></div>}
    {messages.map((row,i)=><article className={'dialogue-message '+row.role} key={row.id||i}><div className="dialogue-avatar">{row.role==='user'?'我':<Waves size={17}/>}</div><div className="dialogue-content"><div className="dialogue-message-label">{row.role==='user'?'你':'海洋声学 Agent'}<button aria-label={'复制第'+(i+1)+'条消息'} title="复制消息" onClick={()=>copy(row.text)}><Copy size={14}/></button></div>{row.role==='user'?<div className="dialogue-user-text">{row.text}</div>:<ChatMessage text={row.text}/>}</div></article>)}
    {busy&&run?.partial&&<article className="dialogue-message"><div className="dialogue-avatar"><Waves size={17}/></div><div className="dialogue-content"><div className="dialogue-message-label">{labels[run.backend||backend]} · 正在回答</div><ChatMessage text={run.partial}/></div></article>}
   </div>
   {run?.trace?.length>0&&<details className="dialogue-trace"><summary>实际工具调用 · {run.trace.length} 次</summary><div>{run.trace.map((item,i)=><details key={i}><summary>{i+1}. {item.tool} · {item.status}</summary><pre>{JSON.stringify(item.arguments,null,2)}</pre></details>)}</div></details>}
   {busy&&<div className="dialogue-runtime" role="status"><Loader2 size={16} className="spin"/>{labels[run?.backend||backend]} · {run?.stage||'正在提交'}{run?.elapsed_seconds!=null&&` · ${run.elapsed_seconds} 秒`}{run?.model&&` · ${run.model}`}<button className="button" disabled={!run?.id} onClick={stop}><Square size={13}/>停止当前请求</button></div>}
   {error&&<div className="dialogue-error" role="alert">{error}<button className="button" disabled={busy} onClick={()=>setText([...messages].reverse().find(row=>row.role==='user')?.text||'')}>编辑上一问题</button></div>}
   <div className="dialogue-composer">{!!messages.length&&<details><summary>从问题库选择问题</summary><QuestionSuggestions mode="agent" onSelect={setText}/></details>}<textarea aria-label="输入问题" placeholder="描述你的研究目标、环境来源与希望得到的结果…" value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send()}}}/><div><span><BookOpen size={13}/>技能 · 教材 · 环境数据 · 真实任务</span><button className="button primary" aria-label="发送问题" disabled={busy||loading||!text.trim()} onClick={send}><ArrowUp size={18}/></button></div></div>
  </section><aside className="panel dialogue-context"><h3>当前工作上下文</h3><p><BookOpen size={18}/>课程知识与教材原页</p><p><FlaskConical size={18}/>模型 Skill 与独立研究任务</p><p><Waves size={18}/>WOA18 温盐声速剖面{cap&&!cap.ocean_data_available&&<small>尚未配置数据目录</small>}</p><div className="dialogue-note">{backend==='dsh'?'DSH 负责规划与执行，通过 MCP 调用工作台工具。凭据由本机 DSH 管理。':backend==='codex'?'使用本机 Codex 登录，持续追问并调用工作台技能和计算工具。':'使用环境设置中的模型接口，按自定义轮数调用工作台工具。'}</div><p className="dialogue-note">清空聊天会创建新会话，可撤销；计算结果保存在“任务与计算结果”。执行成功、数值收敛与物理精度分别判断。</p><button className="button" onClick={openSettings}><Settings2 size={15}/>模型与环境设置</button></aside></div>
 </div>;
}
