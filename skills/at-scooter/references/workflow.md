# SCOOTER 构造与验收流程

## 模型选择与环境

- 当前模型针对距离无关环境；任意起伏海底、沿程变化剖面与三维环境不能直接按单个ENV处理。
- 浅海和深海都可构造，计算代价与谱采样、频率、距离等有关，须验证采样收敛。
- 近场研究要检查fieldsco的变换选项；当前表单默认RP圆柱远场变换，不可直接称作完整近场解。
- ENV前部与KRAKEN同族：介质、声速节点、密度、边界、衰减单位与相速范围。
- ENV中的RMAX控制波数采样，不能只按最终画图距离理解；内部有限元网格与接收深度网格不同。
- SCOOTER的FLP用于谱到距离变换及接收距离。本机MunkS.flp为RP，sductS.flp为RB；选项含义和适用条件需查fieldsco源码。

## 本机基线

算例：TLslices/pekeris。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/TLslices/pekeris.env` → `pekeris.env`
- `tests/TLslices/fields.flp` → `pekeris.flp`

## 专属检查与局限

- 波数积分采样与模态搜索精度不是同一参数。
- FIELDSCO使用本算例匹配的fields.flp，不能沿用KRAKEN的FIELD配置。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `scooter.m`
- `Scooter/fieldsco.m`
- `tests/Munk/MunkS.env`
- `tests/Munk/MunkS.flp`
- `tests/sduct/sductS.env`
- `tests/sduct/sductS.flp`
- `ReadWrite/read_shd.m`
