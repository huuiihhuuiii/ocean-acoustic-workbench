import React,{useState} from 'react';
import {modelWorkflows,modelSkillPrompt} from './modelSkills';
export default function ModelSkillPicker({onSelect,disabled}){
 const [model,setModel]=useState('kraken');
 const recipe=modelWorkflows.find(r=>r.id===model);
 return <details className="chat-model-skills"><summary>模型构造 Skill · 选择模型与创建流程</summary><div className="chat-toolbar"><label>模型流程 <select aria-label="模型构造Skill" disabled={disabled} value={model} onChange={e=>setModel(e.target.value)}>{modelWorkflows.map(r=><option key={r.id} value={r.id}>{r.name}{r.supported?'':' · 暂不可运行'}</option>)}</select></label><button className="button" disabled={disabled} onClick={()=>onSelect(modelSkillPrompt(model))}>构造自定义研究</button><button className="button" disabled={disabled||!recipe.supported} onClick={()=>onSelect(modelSkillPrompt(model,true))}>复现经典算例</button></div><p className="result-note">载入技能 → 检查条件 → 创建输入与脚本 → 实际运行 → 验证与报告。点击先填入消息，发送后执行。{!recipe.supported&&recipe.unavailable_reason}</p></details>
}
