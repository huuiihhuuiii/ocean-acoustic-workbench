# KRAKEN 构造与验收流程

## 模型选择与环境

- 选择依据是频率、波导结构、距离和模态贡献，不存在统一的适用水深上下限。
- 平台表单采用距离无关、单剖面、平底环境；AT的距离相关模态流程需要额外剖面与FIELD配置，不能仅修改一个水深值。
- 近场、泄漏或连续谱贡献重要时，要核对所用模态是否足够；不能只凭算出一个模态就判定模型失效。
- 先给出频率、声速随深度的节点、介质密度、海面与海底边界。逐层核对z、cP、cS、rho、alphaP、alphaS及单位。
- ENV头部选择声速插值、海面边界与衰减单位；本机MunkK.env使用NVW，表单自定义环境使用CVW，二者插值不同，比较前需统一。
- ENV尾部给相速搜索范围、计算控制、源深和接收深度；FLP给模态使用数量、剖面位置、接收距离和场叠加选项。
- 当前WOA18表单的流体半空间模板要求海底声速高于水体最大声速，这是表单限制，并非所有KRAKEN用法的普遍物理条件。

## 本机基线

算例：TLslices/pekeris。输入映射与运行链由 prepare_model_research_task 提供，不能复制旧SHD/GRN/MOD充当新结果。

- `tests/TLslices/pekeris.env` → `pekeris.env`
- `tests/TLslices/fieldbat.flp` → `pekeris.flp`

## 专属检查与局限

- 距离无关Pekeris基线；距离相关研究另查Gulf的RI/AD/CM配置。
- 核对ENV与FLP实际使用的源深、范围和模态截断。

## 完成依据

依次检查进程退出、PRT警告、输出维度与坐标、有限值覆盖；图表注明选定的方位/源深或时间切片。生成的model_metrics.json仅是结构检查。按研究目标补充网格加密、参考解或同环境比较，保留失败记录与尚未解决的差异。提交报告时列出输入与脚本、来源、图表/数值文件、各项检查和结论适用范围。

## 已审阅的原始资料

- `kraken.m`
- `ReadWrite/read_env.m`
- `ReadWrite/write_env.m`
- `ReadWrite/read_shd.m`
- `tests/Munk/MunkK.env`
- `tests/Munk/MunkK.flp`
- `tests/sduct/runtests.m`
- `tests/sduct/sductK.env`
- `tests/sduct/sductK.flp`
