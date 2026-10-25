---
name: surface-duct-investigation
description: 研究季节性表面声道候选结构与声学俘获，从近表层声速诊断到AT环境构造和传播验证，区分混合层、声道结构与有效波导。
---

# 表面声道与传播研究

先载入 seasonal-layer-diagnostics，取得实际温盐声速剖面。复用其脚本得到从海面连续正声速梯度到首个局部极大值的候选声道边界。无连续正梯度、数据截断未见极大值或缺测时分别标记，不把最深层当声道底。混合层厚度和声道厚度分别绘图；声速结构不能独自证明某频率下存在有效声学俘获。

需要传播时载入 at-environment，实际读取 tests/sduct/runtests.m 及 sductK.env/sductK.flp、sductS.env/sductS.flp、sductB.env。用本地原始算例作运行链基准后，替换成研究剖面并保存修改清单。该算例描述泄漏表面声道，不能预设完全俘获。

明确频率、源深、接收深度与距离、海底条件、海面和距离无关假设。缺少关键传播条件时先完成环境诊断，再询问，而不是随意指定海底参数得出真实海域结论。源深在声道内外的对照可分离源深效应。

SCOOTER适合距离无关环境的谱积分分析，但当前表单RP为远场变换，近场研究应核对原始FLP、fieldsco变换选项后独立构造。KRAKEN结果要检查近表层模态形状和衰减；泄漏模态需求须审查KRAKENC或其他适当谱处理，不能只数模态个数判定波导有无。

验证固定环境下采样加密、相干方式、有效覆盖、边界条件、模态/谱积分一致性。报告候选声道深度、频率条件下的能量分布和衰减、泄漏及底质不确定性，保留 ENV/FLP、脚本、PRT、数值和图。参考AT说明：https://oalib-acoustics.org/website_resources/AcousticsToolbox/manual/node63.html 。
