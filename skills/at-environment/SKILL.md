---
name: at-environment
description: 根据本机 Acoustic Toolbox 的 tests 和 MATLAB 源码构造 ENV、FLP 及运行链，复现、扩展和核验声场算例。用于实际 AT 研究与输入格式核对。
---

# AT 环境构造与算例复现

创建指定模型任务时，先载入对应 `at-kraken`、`at-krakenc`、`at-scooter`、`at-bellhop`、`at-ram`、`at-simplepe`、`at-sparc`、`at-bellhop3d` 或 `at-krakel` 技能及其 `references/workflow.md`。使用 list_model_workflows 查创建配方和程序可用性；prepare_model_research_task 在独立目录冻结原例输入并生成脚本，创建后仍须实际运行和验证。其他算例或开放研究按源码构造，不能用默认算例替代用户研究环境。

按模型查用法时先读取 references/models.json，其中分列KRAKEN、KRAKENC、SCOOTER和BELLHOP的适用条件、输入配置、调用流程与验证范围。

研究RAM或PE时读取 references/ram-and-pe.md；查算例目的与入口时先读取 references/casebook-summary.json，再按需读取 references/casebook.json 中的调用行证据。实际运行覆盖见 references/validation-latest.json，包含未收敛观察和读取器问题；跨模型与解析验证的通用规则见 references/validation.md。RAM、SimplePE、SPARC、BELLHOP3D和KRAKEL均单独列在模型经验中，不能把PE、时域、3D输出套入二维单频声场。

先明确物理问题、所需观测量、环境是否随距离变化和数据来源，再选择求解器。选型时先按水深（浅海/深海）× 频段（<500 Hz / >500 Hz）× 距离无关/变化（RI/RD）查 references/applicability.md 的适用性矩阵，再落到具体程序；矩阵是定性经验，收敛仍按专项 workflow 检查。用 list_at_examples 和 read_at_file 查最接近的本机算例，并按需读取 references/input-and-functions.md。索引中的签名只用于发现；使用某函数前读取其源码和测试调用。

在 create_research_task 返回的独立目录复制算例及依赖，保存原始路径、SHA256 与改动清单。用 write_research_file 写运行脚本，再用 run_research_script 实际运行；保持工作目录为任务目录，MATLAB addpath(genpath(AT路径))。源文件保持只读。

先原样复现，再一次只改变明确的研究变量。当前表单无法表达多层、距离相关或特殊声道时，写独立 ENV/FLP 和脚本；不要为了适应表单擅自改研究问题。ENV 选项不能跨求解器直接照搬，读取该求解器的 tests 及 read_env/write_env 分支。

完成标准：检查 exe 返回和 PRT 日志、频率/源深/接收深度/坐标单位、复声压维度与有效覆盖；验证输入冻结一致、采样加密或参考解，并生成输入文件、脚本、PNG、数值 CSV/JSON、检查记录。模态单列/波数标量须显式规范维度。跨模型比 TL 前先对齐相干/非相干/半相干与源归一化，场叠加方式和参考归一化一致后再比较 TL；相位差与干涉极小值不能只看一个全局最大差。

本批仅移植AT模型构造；WOA18、混合层及表面波导数据技能尚未移植，涉及这些数据时先说明缺项。用 finish_research_task 登记方法、假设、证据、产物、验证和局限。求解器运行成功与物理精度验证分别报告。
