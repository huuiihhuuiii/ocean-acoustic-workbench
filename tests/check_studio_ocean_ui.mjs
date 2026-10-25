import {build} from 'esbuild';
import {mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'..'),out=resolve(root,'.local/validation/studio-ocean-ui.cjs');
mkdirSync(resolve(root,'.local/validation'),{recursive:true});
await build({stdin:{resolveDir:root,loader:'jsx',contents:`
import React from 'react';import {renderToStaticMarkup} from 'react-dom/server';import assert from 'node:assert/strict';import {readFileSync,existsSync} from 'node:fs';
import Ocean from './src/OceanData.jsx';import Studio,{initialPlan} from './src/SimulationStudio.jsx';import Results from './src/StudioResults.jsx';
const ocean=renderToStaticMarkup(<Ocean notify={()=>{}} onSimulate={()=>{}}/>);
for(const label of ['海洋环境数据','提取环境剖面','缩放','经度','纬度'])assert(ocean.includes(label),label);
const studio=renderToStaticMarkup(<Studio notify={()=>{}} onSubmit={()=>{}} onAsk={()=>{}}/>);
for(const label of ['KRAKEN','SCOOTER','BELLHOP','WOA18','经典算例','海洋环境'])assert(studio.includes(label),label);
const restored={...initialPlan,template:'woa18',longitude:120,latitude:20,water_depth_m:500,source_depths_m:'100',receiver_depth_m:100};
assert(renderToStaticMarkup(<Studio notify={()=>{}} onSubmit={()=>{}} onAsk={()=>{}} initialEnvironment={restored}/>).includes('WOA18 自定义海洋环境'));
if(existsSync('.local/studio-live-results.json')){
 const cases=JSON.parse(readFileSync('.local/studio-live-results.json','utf8')).cases;
 for(const row of cases){const detail=row.detail;const html=renderToStaticMarkup(<Results initialJobs={[detail]} initialDetail={detail} notify={()=>{}} setActiveJob={()=>{}} setImage={()=>{}} onImportChat={()=>{}}/>);assert(html.includes('删除任务文件'));assert(html.includes('导入对话工作台'));assert(!html.includes('NaN%'));console.log('PASS: actual result UI '+row.name)}
}
console.log('PASS: ocean map controls, full studio defaults, WOA form transfer and result actions');
`},bundle:true,platform:'node',format:'cjs',outfile:out,loader:{'.css':'empty'},logLevel:'error'});
process.stdout.write(execFileSync(process.execPath,[out],{encoding:'utf8'}));
