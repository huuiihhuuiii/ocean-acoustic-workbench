import React,{useEffect,useState} from 'react';

const names={munk_5000m:'Munk 深海声道',pekeris_100m:'Pekeris 理想浅海',woa18:'WOA18 单点环境',constant_5000m:'等声速声线验证'};
export default function SimulationScope({form}){
 const [reports,setReports]=useState({});
 useEffect(()=>{let alive=true;for(const key of ['studio','scooter'])fetch('/api/validation/'+key).then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{if(alive)setReports(v=>({...v,[key]:data}))}).catch(()=>{if(alive)setReports(v=>({...v,[key]:null}))});return()=>{alive=false}},[]);
 const solvers=form.scenario==='model_compare'?['kraken','bellhop']:[form.solver];
 return <section className="simulation-scope" aria-label="适用条件与验证范围"><h3>适用条件与验证范围</h3><p>{names[form.template]} · {solvers.map(s=>s.toUpperCase()).join(' / ')}</p>
 <ul><li>当前接入采用水平分层、距离无关和平底环境；沿传播距离使用同一声速剖面。</li>
 {form.template==='woa18'?<><li>WOA18 温盐数据转换为声速；计算水深须有完整有效剖面覆盖，缺测处不外推。源深和接收深度须小于计算水深。</li><li>海底声速、密度与吸收由用户设定，不来自 WOA18；截断水深不等于真实海底。</li></>:<li>这是理想化教学环境，不代表实测海域；源深与接收深度须位于水中。</li>}
 {solvers.includes('kraken')&&<li>KRAKEN：通过模态计算声场，需要检查模态与数值网格收敛。当前 WOA18 流体半空间模板要求海底声速高于水体最大声速，这是平台模板限制。</li>}
 {solvers.includes('scooter')&&<li>SCOOTER：波数积分相干声场；当前使用 RP 圆柱远场变换。需要检查有限元网格及积分 RMAX 倍数，近源区结果须谨慎解释。</li>}
 {solvers.includes('bellhop')&&<li>BELLHOP：声线与几何波束近似；声场需检查发射角覆盖、波束数和积分步长。声线路径模式不产生传播损失，低频结果不能仅凭运行成功判断可靠。</li>}
 </ul><div className="scope-validation">{solvers.map(s=>{
 const key=s==='scooter'?'scooter':'studio',report=reports[key];
 const records=(report?.records||[]).filter(r=>r.passed&&r.test?.includes(form.template)&&(s==='scooter'?r.test.startsWith('SCOOTER '):r.test.startsWith(s+'_')));
 const analytic=s==='bellhop'&&form.template==='constant_5000m'&&(report?.records||[]).some(r=>r.passed&&r.test==='constant_c_ray_analytic');
 return <p key={s}><strong>{s.toUpperCase()}：</strong>{reports[key]===undefined?'正在读取验证记录…':records.length||analytic?<>{analytic?'已有声线解析直线对照记录':'已有同环境类型的 AT 接入回归记录'}（{report.imported_from?'原平台历史 · ':''}{report.created}）。<a href={'/api/validation/'+key} target="_blank" rel="noreferrer">查看记录</a></>:reports[key]===null?'验证记录暂不可用，当前无法核实。':'已接入此组合；现有验证报告未找到该组合的通过记录。'}</p>
 })}</div><p className="result-note">历史记录只覆盖所测参数，不代表当前输入已验证。接入回归一致、数值稳定和真实海域物理精度是不同结论；当前配置仍需检查并生成计划。</p></section>
}
