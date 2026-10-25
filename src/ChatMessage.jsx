import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import {normalizeChatMath} from './chatMath';

export default function ChatMessage({text}) {
  return <div className="chat-markdown"><ReactMarkdown remarkPlugins={[remarkGfm,[remarkMath,{singleDollarTextMath:true}]]} rehypePlugins={[[rehypeKatex,{trust:false}]]}>{normalizeChatMath(text)}</ReactMarkdown></div>;
}
