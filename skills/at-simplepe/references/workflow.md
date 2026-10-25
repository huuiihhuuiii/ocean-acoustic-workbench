# SimplePE 构造与验收流程

## 模型选择与环境

- 源码包含固定近似与采样设置；不能因为名字含PE就当成RAM同等算法或通用真值。
- 需核对地形范围从0开始及输入单位，检查起始场、海底延拓、频率与角度适用性。
- 读取BELLHOP格式ENV与所需BTY/SSP等，源码将接收距离由km转换为m。
- 源码设置每波长采样数30、海底延拓50个波长和Greene起始场；它们是实现选择，不是自动收敛证明。

## 本机基线

算例：wedge/wedgeB。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/wedge/wedgeB.env` → `wedgeB.env`
- `tests/wedge/wedgeB.bty` → `wedgeB.bty`

## 专属检查与局限

- MATLAB实现，不是RAM包装；其默认离散参数需查simplePE源码。
- 前向PE近似与底部吸收域需单独检查。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `simplePE.m`
- `tests/wedge/runtests.m`
- `tests/wedge/wedgeB.env`
- `tests/wedge/wedgeB.bty`
- `tests/sduct/runtests.m`
