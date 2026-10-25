# RAM 构造与验收流程

## 模型选择与环境

- 需给出传播方向、沿程地形及水体/沉积物剖面，检查步长与计算底部吸收域。
- 大坡度、反向散射或强弹性问题不能仅凭RAM输出就认为近似充分。
- ram.in依次设置频率和源/接收深度、rmax/dr/ndr、zmax/dz/ndz/zmplt、c0/np/ns/rs，再写地形与分段更新剖面。
- ram.in距离与深度均为m，不能把其他AT例子的km距离直接照搬。
- dr/dz是内部网格，ndr/ndz为输出抽样；改变dz可能改变实际输出深度，不能只比较矩阵下标。

## 本机基线

算例：wedge/ram。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/wedge/ram.in` → `ram.in`

## 专属检查与局限

- 先比较分段更新位置 rp 与 rmax，再说明哪段环境实际参与计算。本例 rmax=4000 m，后续 rp=25000 m 超出计算范围，因此不能表述为“本次传播在25 km处更新了剖面”。

- TL网格没有相位；不能恢复复声压。
- 本机深度起点经过探针核对，其他RAM构建应重新确认。
- wedge原始步长尚未证明收敛；输出只证明执行与结构检查。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `ram.m`
- `RAMtoSHD.m`
- `ReadWrite/read_ram_tlgrid.m`
- `ReadWrite/write_env_RAM.m`
- `Slicer/run_ram.m`
- `tests/Dickins/ram.in`
- `tests/wedge/ram.in`
