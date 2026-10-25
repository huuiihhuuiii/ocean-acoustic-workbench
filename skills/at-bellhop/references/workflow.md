# BELLHOP 构造与验收流程

## 模型选择与环境

- 声线路径、相干/非相干声场和到达结构是不同运行类型，按需要选择；声线图本身不提供TL。
- 不能仅按频率数值宣布有效或无效，要结合波长、环境变化尺度、边界和数值稳定性判断。
- BELLHOP本身支持额外地形等输入，但当前表单仍是平底单剖面；复杂环境应独立构造并核验。
- ENV前部描述水体与边界；尾部包含源深、接收深度与距离、运行类型、波束/声线设置、发射角和追踪区域。
- 本机tests/sduct/sductB.env可看到C运行类型、Nalpha、发射角以及STEP/ZBOX/RBOX配置。
- 若引入BTY/SSP等附加文件，须同时检查ENV激活选项、文件单位、坐标方向与覆盖范围。

## 本机基线

算例：free/freePointB。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/free/freePointB.env` → `freePointB.env`

## 专属检查与局限

- 本例为自由空间点源基线；相干声场与声线图使用不同运行选项。
- 声束数和步长需加密检查；阴影区结果需要审慎解释。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `bellhop.m`
- `tests/sduct/sductB.env`
- `tests/sduct/runtests.m`
- `tests/Munk/runtests.m`
