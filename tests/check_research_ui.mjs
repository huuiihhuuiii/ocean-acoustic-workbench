// Component rendering without browser globals or a live backend.
import {build} from 'esbuild';
import {mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'..');
const out=resolve(root,'.local/validation/research-ui.cjs');
mkdirSync(resolve(root,'.local/validation'),{recursive:true});
await build({stdin:{resolveDir:root,contents:`
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import assert from 'node:assert/strict';
import Models from './src/ModelExperience.jsx';
import Result from './src/ResearchResult.jsx';
const models=renderToStaticMarkup(React.createElement(Models,{onAsk:()=>{}}));
for(const name of ['KRAKEN','KRAKENC','SCOOTER','BELLHOP','RAM','SimplePE','SPARC','BELLHOP3D','KRAKEL'])assert(models.includes(name));
assert(models.includes('disabled=""'));
const detail={id:'abcdefabcdef',plan:{objective:'研究目标'},summary:{method:'方法 $c_0$',assumptions:[],inputs:['ram.in'],sources:[],outputs:[{file:'ram_tl.png',bytes:1}],executions:[{file:'run_model.py',exit_code:0,seconds:1}],checks:[{name:'收敛',passed:null,evidence:'未验证'}],conclusion:'仅执行通过',limitations:['缺少独立精度证据']}};
const html=renderToStaticMarkup(React.createElement(Result,{detail,setImage:()=>{}}));
assert(html.includes('/api/jobs/abcdefabcdef/artifact/ram_tl.png'));
assert(html.includes('尚未验证'));assert(html.includes('katex'));
assert(!html.includes('undefined'));
console.log('PASS: nine model cards (KRAKEL restored), generic report, math rendering and task artifact links');
`,loader:'js'},bundle:true,platform:'node',format:'cjs',outfile:out,loader:{'.css':'empty'},logLevel:'error'});
process.stdout.write(execFileSync(process.execPath,[out],{encoding:'utf8'}));
