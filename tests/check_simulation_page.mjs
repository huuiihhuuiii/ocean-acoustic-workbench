import {build} from 'esbuild';
import {readFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
const root=resolve(import.meta.dirname,'..');
const source=readFileSync(resolve(root,'src/main.jsx'),'utf8');
const start=source.indexOf('function Simulation('),end=source.indexOf('function Jobs(',start);
const code=start<0?`import Simulation from './src/SimulationStudio.jsx';`:
 `import React,{useState,useEffect,useRef} from 'react';\n${source.match(/^const initialPlan=.*;$/m)?.[0]||''}\n${source.slice(start,end)}`;
mkdirSync(resolve(root,'.local/validation'),{recursive:true});const out=resolve(root,'.local/validation/simulation-page.cjs');
await build({stdin:{resolveDir:root,contents:`import ReactRoot from 'react';import {renderToStaticMarkup} from 'react-dom/server';import assert from 'node:assert/strict';${code}
const html=renderToStaticMarkup(ReactRoot.createElement(Simulation,{notify:()=>{},onSubmit:()=>{},onResearch:()=>{},onAsk:()=>{}}));
assert(html.includes('声场'));console.log('PASS: actual simulation page initial render');`,loader:'jsx'},bundle:true,platform:'node',format:'cjs',outfile:out,loader:{'.css':'empty'},logLevel:'error'});
process.stdout.write(execFileSync(process.execPath,[out],{encoding:'utf8'}));

