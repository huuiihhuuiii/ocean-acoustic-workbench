# SPARC 构造与验收流程

## 模型选择与环境

- 先定义脉冲、频率范围、输出时刻与时间推进控制，再解释声场结果。
- 须核对GRN及后处理的频率/时间轴和归一化；单个时间切片不代表完整到达过程。
- head.env包含常规层状环境外，还给脉冲选项、FMIN/FMAX、输出时刻及TSTART/TMULT等。
- 先按原始head.env和head.flp复现，输入含多个介质，不能直接用一个水深数字替代。

## 本机基线

算例：head/head。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/head/head.env` → `head.env`
- `tests/head/head.flp` → `head.flp`

## 专属检查与局限

- 输出第一类源深轴在本时域流程实际存储时间，不能解释为多源深。
- 单个时间切片展示相对场幅；未标定源波形前不能直接当单频TL。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `sparc.m`
- `Scooter/fieldsco.m`
- `Sparc/readt.m`
- `tests/head/runtests.m`
- `tests/head/head.env`
- `tests/head/head.flp`
