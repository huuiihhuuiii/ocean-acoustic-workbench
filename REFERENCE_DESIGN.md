# 界面与模型资料来源

核对日期：2026-10-08。以下记录实现依据，便于后续更新。

## 知到 / 智慧树知识图谱参考

参考上海师范大学教务处公开的[智慧树知识图谱使用手册](https://jwc.shnu.edu.cn/_upload/article/files/26/c4/b28fc1cf49408c3fd3980aa81320/2f28c218-42a8-4d05-9ca0-4bc2bea382cc.pdf)，重点查看 PDF 第 164、165、167、169、170 页。界面采用课程单元导航、章节目录、全局 / 局部图谱、节点详情和关系筛选等组织方式。本项目据此设计六个单元的深色课程总览，再展开知识节点；自绘原理图与课程资源相互链接。未复制平台商标或声称为其官方产品。

## 模型预设与端点依据

|API 供应商|本项目模型预设|官方依据|
|---|---|---|
|DeepSeek 官方|DeepSeek-V4.1-Flash → `deepseek-flash`；DeepSeek-V4-Pro → `deepseek-v4-pro`|[模型列表](https://api-docs.deepseek.com/api/list-models/)|
|阿里云百炼 · 北京|`qwen3.8-max`、`qwen3.7-plus`、`qwen3.8-flash`；第三方 `deepseek-v4.1-flash`、`deepseek-v4-pro-0813`、`kimi-k3`、`glm-5.2`|[模型目录](https://help.aliyun.com/zh/model-studio/models)、[OpenAI 兼容接口](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)|
|月之暗面 Kimi 官方|`kimi-k3`、`kimi-k2.7-code`、`kimi-k2.7-code-highspeed`、`kimi-k2.6`|[模型文档](https://platform.kimi.com/docs/models)、[API Key 与端点](https://platform.kimi.com/docs/get-api-key)|
|智谱 BigModel 官方|`glm-5.3`、`glm-5.3-flash`、`glm-5.3-flashx`|[模型总览](https://docs.bigmodel.cn/cn/guide/start/model-overview)、[GLM-5.3](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3)、[GLM-5.3-Flash](https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash)|

供应商与开发方是两个字段。通过百炼调用第三方模型，需要百炼 API Key 及对应地域 / 服务权限，不能直接填入模型开发方的官方 Key。百炼目前也提供业务空间专属域名，界面允许填写；预设使用文档保留支持的北京旧兼容地址。

“官方文档已核对”表示模型名称和接口方案有官方依据，不表示当前用户账户已开通、余额足够或模型实际调用成功。本轮没有提供密钥，因此未向这些供应商发出实际推理请求。视觉和工具能力描述来自供应商文档；当前工作台聊天仍使用文字及项目读取工具，尚未实现图片上传、任意代码修改和自动修复。

## 知识内容与图片

知识点主要依据资料包英文《Computational Ocean Acoustics, Second Edition》对应 PDF 原页，以及 ASIAEX / SW06 报告和 AT 源文件。PDF 页号与书内印刷页号不同，界面统一注明 PDF 页号。课程分类和建议阅读顺序为人工教学整理；概念关联不统一解释为因果关系。

十张自绘 SVG 用于讲解声学量、扩展损失、剖面、边界、传播方法、模态、射线、工具流程、网格和观测流程。示意图不作为求解器输出；Munk 剖面的离散点直接来自教师 `MunkK.env`。实际计算图只出现在任务结果中，并关联本次输入、输出与日志。
