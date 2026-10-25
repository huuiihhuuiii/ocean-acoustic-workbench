export const projectCategories = [
  ['code', '程序与脚本'],
  ['inputs', '模型与环境输入'],
  ['results', '图表与计算数据'],
  ['docs', '说明、报告与日志'],
  ['tests', '测试与校验'],
];

export function projectCategory(file) {
  const path = file.path.toLowerCase();
  const name = path.split('/').at(-1);
  const extension = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
  if (path.startsWith('@workbench/tests/')) return 'tests';
  if (['.env', '.flp', '.bty', '.ati', '.ssp', '.brc', '.irc', '.sbp', '.in'].includes(extension)
      || ['case.json', 'environment.json', 'profiles.json', 'workflow.json', 'ssp.csv'].includes(name)) return 'inputs';
  if (['.md', '.txt', '.log', '.prt'].includes(extension)
      || ['summary.json', 'research_report.json', 'executions.json', 'provenance.json'].includes(name)) return 'docs';
  if (['.py', '.m', '.jsx', '.js', '.css'].includes(extension)) return 'code';
  if (['.png', '.svg', '.csv', '.json', '.shd', '.mod', '.grn', '.mat', '.grid', '.npz', '.ray', '.line'].includes(extension)) return 'results';
  return 'docs';
}
