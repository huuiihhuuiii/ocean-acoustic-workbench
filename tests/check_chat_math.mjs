import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import {normalizeChatMath} from '../src/chatMath.js';
const render=text=>renderToStaticMarkup(React.createElement(ReactMarkdown,{remarkPlugins:[[remarkMath,{singleDollarTextMath:true}]],rehypePlugins:[[rehypeKatex,{trust:false}]],children:normalizeChatMath(text)}));
for(const [name,text,display] of [
 ['model inline',String.raw`参考场 \(P_{\mathrm{ref}}\)。`,false],
 ['model display',String.raw`公式：\[\mathrm{TL}=-20\log_{10}\frac{|P|}{|P_{\mathrm{ref}}|}\]`,true],
 ['dollar inline',String.raw`波数 $k=\omega/c$。`,false],
 ['dollar display',String.raw`$$\frac{a}{b}$$`,true],
]){
 const html=render(text);
 assert.ok(html.includes('class="katex"'),name+' must render math');
 assert.equal(html.includes('katex-display'),display,name+' display mode');
 assert.ok(!html.includes('katex-error'),name+' invalid math');
}
const code=String.raw`示例 \(x^2\)。`;
assert.equal(normalizeChatMath('```latex\n'+code+'\n```'),'```latex\n'+code+'\n```');
assert.equal(normalizeChatMath('`'+code+'`'),'`'+code+'`');
assert.ok(!render('`'+code+'`').includes('class="katex"'));
console.log('PASS: model and dollar delimiters, inline/display modes, protected code');
