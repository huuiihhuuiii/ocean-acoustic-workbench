import React,{useState} from 'react';
import {RotateCcw,ArrowUpRight} from 'lucide-react';
import {questionBank,agentQuestions,nextQuestions} from './questionBank';

export default function QuestionSuggestions({mode,onSelect}) {
  const bank=mode==='agent'?agentQuestions:questionBank;
  const [questions,setQuestions]=useState(()=>nextQuestions(bank));
  return <section className="question-suggestions" aria-label="推荐问题库"><div className="question-heading"><span>推荐问题 <small>{bank.length} 个问题</small></span><button type="button" onClick={()=>setQuestions(old=>nextQuestions(bank,old))}><RotateCcw size={14}/>换一组</button></div><div className="prompt-grid" aria-live="polite">{questions.map(([topic,text])=><button type="button" key={text} onClick={()=>onSelect(text)}><span><small>{topic}</small>{text}</span><ArrowUpRight size={17}/></button>)}</div></section>;
}
