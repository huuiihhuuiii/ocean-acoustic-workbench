# KRAKENC 构造与验收流程

## 模型选择与环境

- 研究泄漏模态或弹性介质材料衰减时，需考虑KRAKENC与KRAKEN的处理差别，并核对具体边界和模型假设。
- 复根搜索范围、根的完整性和所选模态贡献均需验证；更换求解器名称不保证得到正确或完整声场。
- 距离相关环境仍需额外配置FIELD连接各局部环境；本机存在wrapper不等于现有表单已提供这种能力。
- ENV/FLP结构与KRAKEN同族；从对应KRAKENC算例复制后，检查插值、边界、材料衰减单位和相速搜索范围。
- tests/MunkLeaky/MunkKleaky.env包含带吸收的流体海底半空间及较宽相速搜索范围，可用于理解不同模态贡献；其数值不是任意海域的默认参数。
- 源深、接收深度及FIELD参数须相容。每次改环境后重新计算模态，不复用旧MOD声称是新输入结果。

## 本机基线

算例：MunkLeaky/MunkKleaky。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/MunkLeaky/MunkKleaky.env` → `MunkKleaky.env`
- `tests/MunkLeaky/MunkKleaky.flp` → `MunkKleaky.flp`

## 专属检查与局限

- 复模态搜索范围影响泄漏模态的纳入。
- 本例相速度上限20000，不是任意环境默认值；先做搜索范围与网格敏感性检查。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `krakenc.m`
- `krakenc_nofield.m`
- `tests/MunkLeaky/runtests.m`
- `tests/MunkLeaky/MunkKleaky.env`
- `tests/MunkLeaky/MunkKleaky.flp`
