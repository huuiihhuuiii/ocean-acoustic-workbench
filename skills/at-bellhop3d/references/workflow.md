# BELLHOP3D 构造与验收流程

## 模型选择与环境

- 需要定义源x/y/z、接收方位/距离/深度以及二维角扇。
- 三维海底和区域输入的坐标、单位、覆盖与波束近似须单独检查，free算例通过不证明所有区域算例可用。
- freeBhat.env显式给源水平坐标、方位角、Nalpha/Nbeta、角扇及x/y/z追踪边界。
- 保持压力输出中的方位和其他轴语义，不能固定取第一个方位后称完整三维结果。

## 本机基线

算例：Bellhop3DTests/free/freeBhat。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/Bellhop3DTests/free/freeBhat.env` → `freeBhat.env`

## 专属检查与局限

- 输出含方位维度；默认只展示第一个方位与第一个源深。
- 三维地形、方位采样与射线扇区还需独立验证。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `bellhop3d.m`
- `tests/Bellhop3DTests/runtests.m`
- `tests/Bellhop3DTests/free/runtests.m`
- `tests/Bellhop3DTests/free/freeBhat.env`
