# 已审阅的本机入口

以下依据本机源码和 tests 审阅；不是对所有 AT 版本的通用接口保证。

| 入口 | 本机调用与产物 | 对应参考 |
|---|---|---|
| kraken('case') | kraken.exe → field.exe；.env/.flp → .mod/.shd，前缀不带扩展名 | tests/Munk/MunkK.env、MunkK.flp；tests/sduct/sductK.env |
| scooter('case') | scooter.exe → fieldsco('case.grn')；产物通常 .shd.mat | tests/Munk/MunkS.env；tests/sduct/sductS.env、sductS.flp |
| bellhop('case') | bellhop.exe；根据运行选项产出声线、声场或到达结构 | tests/Munk/runtests.m、tests/sduct/runtests.m |
| read_env | 返回 TitleEnv,freq,SSP,Bdry,Pos,Beam,cInt,RMax,fid；读取后检查句柄管理 | ReadWrite/read_env.m |
| write_env | envfil,model,TitleEnv,freq,SSP,Bdry,Pos,Beam,cInt,RMax；按model分支写尾部 | ReadWrite/write_env.m |
| read_shd | PlotTitle,PlotType,freqVec,atten,Pos,pressure；显式传扩展名，核对数组轴 | ReadWrite/read_shd.m |
| fieldsco | 从GRN进行谱积分；本机单参数入口会读取对应FLP | Scooter/fieldsco.m |

## ENV/FLP 核对

ENV 通常包括标题、频率、介质层数、海面/插值/衰减单位选项，各层网格/粗糙度/底深和 z,cP,cS,rho,alphaP,alphaS，底边界及半空间。简写行会继承默认值，不能仅凭缺列猜测；查看解析函数。

KRAKEN 尾部为相速搜索范围、RMAX、源深和接收深度；FIELD 的 FLP 控制叠加方式、模态数、剖面位置、接收距离等。SCOOTER 使用其 ENV 指定谱采样控制，再由 fieldsco 的 FLP 指定变换/距离。tests/sduct/sductS.flp 的 RB 与当前表单 RP 并非同一个变换设置，近场比较前必须核对；不能直接沿用表单远场近似声称已计算完整近场。

## 算例选择

- tests/sduct：实际标题 Leaky surface duct，K/B/S 运行链都在 runtests.m；先检查其声速剖面和泄漏特征。该算例不是 WOA18 观测。
- tests/Munk：深海声道及多模型流程。
- tests/PekerisRD：runtests.m 主要演示 BELLHOP 距离相关底质，不能因目录名就认定已有 KRAKEN 距离相关复现。
- tests/SedAtten：沉积物衰减规律对照；频率和衰减单位须成对保持。
- 其他目录和函数需通过索引检索后审阅；当前未逐项执行验证。
