export function taskChatDraft(task) {
  if(task.plan.kind==='research')return {id:crypto.randomUUID(),mode:'agent',text:`请读取并分析自定义研究任务 ${task.id}：${task.plan.title}。目标：${task.plan.objective.slice(0,2000)}。先get_job核对报告与状态，再读取相关脚本、图表和数据，说明结论与验证局限。`};
  const {environment_snapshot,research_base,...plan}=task.plan;
  const {environment,...summary}=task.summary||{};
  const data={id:task.id,state:task.state,created:task.created,updated:task.updated,plan,summary,error:task.error,
    environment:environment_snapshot?{water_depth_m:environment_snapshot.water_depth_m,ssp_rows:environment_snapshot.ssp?.length,bottom:environment_snapshot.bottom,assumptions:environment_snapshot.assumptions}:undefined};
  return {id:crypto.randomUUID(),mode:'agent',text:`请分析任务 ${task.id} 的计算数据，说明输入条件、主要结果、可靠性与下一步建议。先调用 get_job 核实最新状态与完整冻结环境；需要对比时逐个读取相关任务。以下是导入时的任务摘要，状态与结果以本次工具查询为准：\n\n${JSON.stringify(data,null,2)}`};
}
