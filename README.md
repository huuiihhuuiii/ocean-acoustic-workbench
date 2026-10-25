# 海洋声学工作台 · v0.7

用于四人小组的海洋声学课程作业与教学展示，无任何商业用途。React 网页、FastAPI 计算节点与云端 Worker 分工运行；实际仿真由获授权的 MATLAB R2024a 调用 AT KRAKEN / FIELD 完成。项目原创代码采用 MIT 许可证，外部教材、AT 与 MATLAB 保留各自权利和许可。

公开网页：[海洋声学工作台](https://ocean-acoustics-workbench-30682.jovial-sun-4182.chatgpt.site/)。云端页面、课程图谱、课程卡/公开海洋知识检索与模型连接不依赖维护者电脑；MATLAB 仿真和私有教材全文索引需要计算节点在线。

## 界面与使用

公共网页与本地管理前端共用课程目录、图谱画布、知识详情和聊天组件。v0.7采用 Fuwari 样式改编、Sakana 动画核心与原创透明海洋研究员插画，保留上游 MIT 许可；未移植默认动漫角色或官方 Logo。模型、上下文、更多和发送集中在输入框底部，默认“资料 + 模型知识”。说明见 [NOTICE](../NOTICE.md)与 `src/vendor/`。

- **知识图谱**：6 个课程单元、46 个知识点，53 个节点和 126 条有类型的关系。直接点击查看概念、公式、适用条件、图片和引用，无需调用大模型。课程层级、建议阅读顺序与概念关联分别展示，关系连接不等于物理因果。收藏和已读标记只表示浏览器中的操作记录。
- **知识库与对话**：课程卡、术语别名、一跳关联、私有原页及公开网页共同提供证据。默认“资料 + 模型知识”（`general`）保留模型已有能力并单列未经资料核验的补充；“更多”可切换“仅依据资料”（`course`），普通空检索时明确缺口。未配置 API Key 时只显示检索证据，图谱和公开来源可直接阅读。
- **输入预算**：4K、8K、16K、32K、64K、128K，自动 32K；服务端实际裁剪历史与资料，并记录估算输入、裁剪情况和供应商实际用量。这个输入预算不改变模型原生窗口或 KV cache，未返回的实际缓存用量保持未知。
- **公开海洋资料**：30 篇 NOAA 正文与 9 条项目自写导读，共 39 个可检索来源、67 个片段。42 项登记中 3 项仅为动态入口，尚未读取实时值。图谱“学习资源”显示来源、机构、更新时间、取得时间和许可；中文导读不是官方译文。
- **模型快切与小航**：主问答与原创海洋助手共用本人的对话、模型选择与知识范围，聊天内切换已配置供应商的模型并记录请求/响应标识。公网端使用真实 SSE 文本增量、停止与截断状态，支持分别保存的持久会话；本地聊天兼容常规完整响应。
- **资料缺口**：没有匹配资料的问题进入待补资料记录；公网记录绑定当前访客并加密存储，不公开给其他访客，也不自动进入正式课程图谱或训练模型。
- **课程命题与仿真**：12道命题包含9道参数预设和3道条件/边界题。自然语言只解析显式参数与单位，缺项保留；先形成草案、预览组合，再由用户确认固定模板计算，不自动启动。完成后查看声场图、曲线、实际网格和文件哈希，并可核查2–4个成功任务的可比性。
- **项目阅读**：本地管理员可浏览授权目录内的文本项目；公共 Agent 只分析课程共享模板。自动修改 MATLAB 代码、自由执行命令和读取访客设备文件尚未实现。
- **模型设置**：DeepSeek、阿里云百炼、Moonshot Kimi、智谱 GLM 的16个预设列出具体名称、API标识与端点。模型列表与短连接测试需自己的有效Key，短生成可能产生费用；目录预设不表示账户已开通权限或本轮已做真实付费调用。
- **Sites个人与小组空间**：平台登录身份提供跨设备个人会话与配置；匿名空间不自动合并。课题邀请只共享显式研究笔记与来源链接，不共享成员的Key、私人对话或私有教材。该账户/课题服务位于公网Worker，本地管理端继续使用本机授权环境。

## 知识入库的实际范围

S01、S07、S15、S17、S18五份授权PDF已处理1846页，1789页入库。v0.7按保留Unicode的入库格式2重建为4101个私有片段；57页为空/短文本待复核。历史4092是旧格式结果。约96.9%的文本层入库页覆盖率不代表知识正确率、公式/表格已核验或其他课程资料已入库。46个人工知识点保留为概念层，全文页不必全部挂入图谱。

节点采用BM25、双语术语、概念优先与有语境的口语拆问，规则命中时最多四路候选排行做真实RRF。精准人工卡不被同页多个原文片段挤出，实际相关原文优先于宽泛图谱邻居；缓存复用分词与BM25统计。分块保留来源、PDF实际页、显示字符位置和文件SHA-256，NFKC只在检索字段使用。旧索引的上/下标损失无法反推，须从授权原文重建。

公开网页使用官方正文快照、项目中文别名与导读；节点离线时仍可检索内置公共内容。所有引用均为候选，尚未自动逐句核验回答蕴含关系；指定时间、海域、深度的数值缺少匹配观测时明确拒绝冒充实测。60题基准检查召回、来源定位与门控，属于经开发调参的回归，不是盲测或回答准确率。详见 [KNOWLEDGE_QUALITY.md](../docs/KNOWLEDGE_QUALITY.md)。

导入器支持 PDF、DOCX、UTF-8 TXT 和 Markdown。省略清单的 `pages` 字段即可逐页处理该来源，教材正文索引放在 `.local/kb/chunks.sqlite3`，不提交 GitHub。57 页 `blank_or_short` 不等于已确认扫描页；没有执行 OCR、向量检索、自动物理关系抽取或模型训练。官方白名单的网页刷新已实现，通用实时全网搜索和实时观测 API 尚未接入。详见[私有入库](../docs/KNOWLEDGE_IMPORT.md)、[公开来源与刷新](../docs/OPEN_OCEAN_KNOWLEDGE.md)和[方法借鉴](../docs/KNOWLEDGE_EXPANSION.md)。LightRAG 等完整框架未安装；直接复用 BM25 评分器的原许可保留在 `backend/vendor/`。

节点启动与状态查询调用 `public_ocean.refresh_if_stale(ttl_hours=168, background=True)`，只在后台检查批准的官方 URL，并更新独立 `.local/kb/open-ocean/snapshot.json`。失败保留上次成功版本，不覆盖课程 SQLite。需要将公开快照导出到开源包时运行 `python backend/public_ocean.py --publish --ttl-hours 168`，随后重新构建发布；正常搜索不等待网络。

## 本地启动与环境

在已经配置好本机依赖与资源的电脑上，双击 `启动工作台.cmd` 打开 `http://127.0.0.1:8765/`，或执行 `./start.ps1 -NoBrowser`。启动器会复用正在运行的服务；后台日志为 `.local/server.stderr.log`。

换电脑需要 Python 3.12+、Node.js 22.13+、获授权的 MATLAB、AT 与自己有权使用的课程资料。原始资料和安装包不随公开源码分发。

声场计算依赖**外部** AT 工具箱（`toolbox_path`，含 `bin/` 与 MATLAB 封装）与 WOA18 海洋数据（`ocean_data_path`，含 `ssp/`、`terrain/` 结构），二者不随仓库分发，须在环境设置中指向本机目录。

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm.cmd ci
npm.cmd run build
./.venv/Scripts/python.exe backend/bootstrap.py "你的资料包路径.zip"
./start.ps1
```

在环境设置中填写 MATLAB 可执行文件、AT 与授权项目目录，再检查环境。开发时分别运行 `backend/app.py` 和 `npm.cmd run dev`；本地 API 文档在 `/api/docs`。当前机器的启动器读取 `.local/runtime.json`，不修改系统 Python。

AT 使用 MATLAB 搜索路径方式接入，不是 `.mltbx` 安装包。安装脚本将资源导入当前用户 `Documents/MATLAB/AcousticsToolbox/at`，为 `startup.m` 登记根目录、`bin`、`ReadWrite`、`Plot` 和 `Misc` 并保留备份。既有节点已验证相关函数位置；迁移后须重新检查自己的环境。

AT 工具箱本身不随仓库分发，需自备官方发行版（本机配套副本在桌面 `AcousticsToolbox`，约 115 MB，已剔除 tests 的生成结果）。本机对 AT 的唯一改动：官方 2018 发行版缺 `krakel.exe`，已用 2026-10-22 源码重新编译（`Krakel/krakel.f90` 修正 4 处接口调用以匹配同版本 `misc`，物理逻辑未改）后放入 `bin/`；其余 11 个 exe 为官方原版。需要弹性模态时，把 `toolbox_path` 指向含该 `krakel.exe` 的 AT 目录即可。

## 真实计算与结果边界

网页参数 → 严格 Plan 校验 → 独立任务目录 → 数值 `case.json` → 固定入口 `backend/matlab/run_ocean_case.m` → ENV / FLP → 读取 ENV 核对输入 → KRAKEN / FIELD → SHD 复声压 → TL、曲线与数值验证 → PNG、CSV、JSON 和 `manifest.json`。

当前只支持 5000 m Munk 距离无关模板、10–200 Hz、位于水面与海底之间的源/接收深度、0.1–100 km 距离。公网单批最多 4 组；本地管理端单批最多 12 组。频率和源深扫参去重，未知字段、非有限数值与越界输入被拒绝。接收深度使用最近网格点，并同时记录请求值、实际值和偏差。

TL 使用 FIELD 归一化压力计算 `TL = -20 log10 |p|`，近零声压对应样本被屏蔽；固定 40–110 dB 色标用于展示。结果检查坐标排序、范围、采样点数、矩阵轴顺序、真实频率/源深、接收曲线对应行和有效比例。manifest 记录输入、脚本及产物哈希；未报告的 KRAKEN/FIELD 版本保留为未知。

数值卡来自本次结果，不预测或捏造TL。相干曲线无需随距离单调增加，不同取样条件的中位数不能用于海域排名。对比接口只接收2–4个成功任务，检查环境、完整网格、归一化、有限样本与产物哈希；检查不通过时不给出可比结论。这些检查不证明数值收敛，也不替代真实观测、校准或实验验证。

SQLite持久保存任务、批次、状态事件、暂停状态和提交幂等标识，事务领取与单执行器锁防止重复计算；数据库升级前生成一致性备份。重启保留QUEUED任务，孤立RUNNING标记INTERRUPTED并暂停，管理员核对残留进程后恢复。相同幂等标识与参数返回已有任务，修改参数需新标识；不会自动重跑状态不明的MATLAB。草案、预览和对比均不执行任意生成代码。

## 公网部署与密钥存储

运行 `启动公网计算节点.cmd` 或 `start-public.ps1 -NoBrowser`，启动本地服务、回环地址上的受限访客网关与主动发起 HTTPS 请求的云端连接程序。无需开放本机公网入站端口，也不依赖临时隧道；节点必须联网且不休眠。完整网页与云端源码在相邻 `ocean-acoustic-public` 目录，部署配置见[部署说明](../docs/DEPLOYMENT.md)。

公网模型请求由云端Worker直连供应商。个人模型配置与独立会话在D1加密持久保存，节点重启不会清除；支持清除本人Key。匿名空间绑定浏览器Cookie；Sites登录后使用账户个人空间，可跨设备访问本人会话和配置，匿名内容不自动迁入。共享课题有独立成员权限，只共享明确提交的笔记/来源链接，不共享Key、私人会话和私有原文。

图谱、模型目录、课程卡和公开海洋知识包在云端提供；已提供的教材页图片可缓存至 R2。节点离线时 MATLAB 与私有教材全文索引不可用，云端课程卡、公开网页检索与已配置模型问答仍可使用。网页快照不是实时海况，原页最近更新也不能证明其中历史数值已更新。

本地管理员的模型密钥仍保存在 `.local/config.json` 与 `.local/model-profiles.json`，并不会自动变成公共访客的密钥。连接密钥在 `.local/public-runtime.json`，同时作为云端运行时 Secret；本地资料、密钥、数据库、原文索引和求解产物均不上传 Git。

## 验证

当前检查范围见 [VALIDATION_V0_7.md](../docs/VALIDATION_V0_7.md)，历史公开知识/预算与全文验收保留在 [v0.6](../docs/VALIDATION_V0_6.md)和[v0.5](../docs/VALIDATION_V0_5.md)。本轮未发送真实付费生成；模拟SSE或无效Key认证层探测不能代替供应商生成质量验证。OCR、向量、模型训练、实时观测、通用全网搜索和任意代码Agent仍未实现。

```powershell
./.venv/Scripts/python.exe tests/test_knowledge.py
./.venv/Scripts/python.exe tests/test_knowledge_quality.py
./.venv/Scripts/python.exe tests/test_public_ocean.py
./.venv/Scripts/python.exe tests/test_context_budget.py
./.venv/Scripts/python.exe tests/test_science.py
./.venv/Scripts/python.exe tests/test_models.py
./.venv/Scripts/python.exe tests/test_plans.py
./.venv/Scripts/python.exe tests/test_persistence.py
./.venv/Scripts/python.exe tests/test_simulation.py
./.venv/Scripts/python.exe tests/test_simulation_api.py
./.venv/Scripts/python.exe backend/evaluate_knowledge.py
# 云端逻辑离线测试：在相邻 ocean-acoustic-public 目录运行 npm.cmd test
# 以下检查需要本地服务、课程资料和已有成功计算结果：
./.venv/Scripts/python.exe tests/check_local.py
./.venv/Scripts/python.exe tests/check_references.py
```

模型选择与配置入口参考 [WorkBuddy 官方说明](https://www.codebuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Model)，未复制其产品或角色。供应商缓存以 [DeepSeek](https://api-docs.deepseek.com/zh-cn/guides/kv_cache/)和[百炼](https://help.aliyun.com/zh/model-studio/context-cache)官方文档为准，本项目不控制该缓存或保证命中。


## 本机研究增强（feature/research-agent 开发分支）

本分支在 v0.7 上移植模型 Skill、独立研究脚本执行和通用结果报告，尚未发布到 main。声场仿真页列出 9 类模型经验，8 类有基线创建配方；KRAKEL的 krakel.exe 已由官方源码编译并冒烟通过，弹性场后处理待验证。知识问答已替换为完整“对话工作台”，移除浮动课程助手；固定 Munk 队列与研究任务仍分别管理。

研究 Agent 可使用完整 DSH Agent、本机已登录的 Codex，或当前配置的模型 API。DSH 通过 ACP 驱动并以 MCP 调用工作台工具，凭据仍由 DSH 管理。需已安装相应 CLI/桌面应用或配置模型 Key，并填写 MATLAB 与 AT 路径。脚本实际运行于本机授权目录，不是安全沙箱；仅用于自己的受信任研究任务，不向公共访客开放任意代码执行。

新请求通过 /api/research/chat 提交，轮询 /api/research/runs/ID 获取实际进展；请求ID幂等，重复请求不重复启动计算。模型Skill创建输入、脚本和溯源，执行后核对输入版本、产物及报告；运行成功不等于收敛或物理精度已获证明。研究结果与固定模板在同一任务页展示，但使用独立research_jobs表，避免模板执行器误领取研究任务。停止回答和取消计算分别操作；重启后的未完成研究标为中断，不自动重跑。

已迁入原对话的技能选择、可刷新问题库、公式渲染、工具进度、停止、聊天导出/清空/撤销与任务导入；补齐教材原页检索、WOA18 剖面读取及混合层/表面声道研究技能。现已完整迁入海洋地图和声场仿真表单；没有复制旧数据库、聊天历史或密钥；本机海洋数据通过私有目录映射读取，不随 Git 分发。Skill内的2026-10-22算例覆盖记录属于移植前的历史证据，不能当作本次移植重新执行。

基础检查：`python -m unittest discover -s tests -p "test_*.py"`。会话归档、长历史、工具升级和RAM读取器回归位于 tests/check_codex_*.py 与 tests/check_ram_grid.py。真实声学链还需在具备MATLAB/AT的环境单独验证。


DSH 本机兼容性与数据配置：已验证 DSH Desktop 0.12.1（Harness 0.2.1-rc.2），尚未验证其他版本及非 Windows 系统。安装位置可用 `OCEAN_DSH_EXECUTABLE` 覆盖，凭据根目录可用 `OCEAN_DSH_HOME` 覆盖；当前 ACP 默认模型为 deepseek-v4-flash，并非自动同步 Desktop 界面选择。提供商需有有效凭据与额度。

WOA18 接口需要安装 requirements 中的 netCDF4 和 gsw，并在私有 `.local/config.json` 中设置 `ocean_data_path`，目录内保留 `ssp` 和 `terrain` 结构。Windows 的 NetCDF 库在本机无法打开中文路径，需使用英文路径的目录联接（Junction）；设置后重启服务。首次克隆者自行准备获授权数据，勿复制他人的私有配置。当前预览前端 5173，API 8766。

本次完整替换的详细证据见仓库根目录 `docs/MIGRATION_RESEARCH_AGENT.md`。


声场与环境完整迁移：声场页和结果页已独立封装，支持 KRAKEN/SCOOTER/BELLHOP、经典环境和 WOA18，以及扫描/对比/稳定性分析；海洋环境页支持地形地图缩放拖动选点、剖面导出与传入声场配置。新版扩展仿真 API 使用 `/api/simulation` 前缀，继续使用持久计算队列。六组真实运行记录见 `/api/validation/migration`，历史原平台报告另有标记。`node tests/check_simulation_page.mjs` 用于捕捉页面初次渲染崩溃；不能仅以生产构建通过代替此检查。
