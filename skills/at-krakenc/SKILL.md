---
name: at-krakenc
description: 使用KRAKENC构造独立声学研究任务，核对输入与后处理，实际运行并检查结果。适用于明确选择KRAKENC或需要判断该模型适用性的研究。
---

# KRAKENC 任务创建

先读取本技能的 references/workflow.md。目标未明确时先确定观测量、频率、环境来源和传播几何；用户只查用法时直接解释，无需启动计算。

原例复现使用 list_model_workflows 核对本机可用性，再 prepare_model_research_task(model="krakenc", case="MunkLeaky/MunkKleaky", title=任务标题, objective=用户目标)。此工具只创建独立输入、运行脚本和溯源记录，尚未运行。返回阻塞时如实说明缺项。

创建成功后核对 workflow.json 与实际输入，使用 run_research_script 运行返回的 runner；检查日志、model_metrics.json、图表和数据。完成后用 finish_research_task 提交报告，将执行成功、数值稳定和物理精度分别报告。读取结果用 get_job 与 read_project_file。

自定义环境先原样复现，再通过 write_research_file 修改任务副本并记录变量、单位和假设。读取 at-environment 的 references/input-and-functions.md 及本机 read_at_file 对应源码；模板不能表达研究几何时，按已查证的调用链改写脚本。finish_research_task 会核对实际输入版本；修改后须重跑。
