import Simulation from './SimulationStudio';
import {projectCategories,projectCategory} from './projectFiles';
import './project-files.css';
import Jobs from './StudioResults';
import OceanData from './OceanData';
import PageErrorBoundary from './PageErrorBoundary';
import ModelExperience from './ModelExperience';
import DialogueWorkbench from './DialogueWorkbench';
import {taskChatDraft} from './taskChat';
import ResearchResult from './ResearchResult';
import './research-agent.css';
import React, { useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";
import GraphExplorer from "./GraphExplorer";
import ModelPanel from "./ModelPanel";
import { ChatProvider, useChatSession } from "./chat-session";
import RichMessage from "./RichMessage";
import ResearchWorkspace from "./ResearchWorkspace";
import { AccountBadge, AccountProvider } from "./account";
import OceanProfile from "./OceanProfile";
import { SimulationAssistant, JobComparison } from "./SimulationAssist";
import {
  Waves,
  Users,
  MessageSquare,
  Network,
  FlaskConical,
  FolderCode,
  Settings2,
  Activity,
  ArrowUpRight,
  ChevronRight,
  Search,
  Maximize2,
  Plus,
  Minus,
  RotateCcw,
  BookOpen,
  ExternalLink,
  ArrowUp,
  Play,
  Pause,
  Check,
  AlertCircle,
  X,
  Download,
  FileText,
  Terminal,
  GitBranch,
  SlidersHorizontal,
  Image as ImageIcon,
  Loader2,
  CheckCircle2,
  Save,
  PanelRightClose,
} from "lucide-react";
import "./style.css";
import "./workbench.css";
import "./ocean-theme.css";
import "./vendor/fuwari.css";
import "./anime-theme.css";
import "./ui-polish.css";
const api = async (path, options = {}) => {
  const r = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: r.statusText }));
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return r.json();
};
const stateName = {
  QUEUED: "排队中",
  RUNNING: "运行中",
  SUCCEEDED: "已完成",
  FAILED: "失败",
  CANCELLED: "已取消",
  INTERRUPTED: "执行中断",
};
const relationName = {
  has_boundary: "边界条件",
  affects: "影响",
  formed_by: "组成",
  requires: "需要",
  differs_from: "不同于",
  calls_after_kraken: "随后调用",
  has_axes: "数据维度",
  observes: "观测",
};
const pages = [
  ["graph", "知识图谱", Network],
  ["chat", "对话工作台", MessageSquare],
  ["ocean", "海洋环境数据", Waves],
  ["simulation", "声场仿真", FlaskConical],
  ["jobs", "任务与结果", Activity],
  ["workspace", "共享课题", Users],
  ["project", "项目文件", FolderCode],
];
const classes = {
  声学原理: "#15868e",
  工具与数据: "#657bac",
  实验观测: "#b48747",
};
function Button({
  children,
  onClick,
  variant = "",
  disabled = false,
  type = "button",
  title,
  ariaLabel,
}) {
  return (
    <button
      type={type}
      title={title}
      aria-label={ariaLabel}
      disabled={disabled}
      className={"button " + variant}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
function Field({ label, unit, hint, children }) {
  return (
    <label className="field">
      <span>
        {label}
        <small>{unit}</small>
      </span>
      {children}
      {hint && <em>{hint}</em>}
    </label>
  );
}
function Badge({ state }) {
  return (
    <span className={"badge " + state.toLowerCase()}>
      <i />
      {stateName[state]}
    </span>
  );
}
function App() {
  const chat = useChatSession();
  const [page, setPage] = useState("graph");
  const [initialKnowledge, setInitialKnowledge] = useState(null);
  const [health, setHealth] = useState(null);
  const [toast, setToast] = useState("");
  const [image, setImage] = useState(null);
  const [refresh, setRefresh] = useState(0);
  const [activeJob, setActiveJob] = useState(null);
  const [initialSimulation, setInitialSimulation] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pendingNote, setPendingNote] = useState(null);
  const [researchDraft,setResearchDraft]=useState(null);
  const [oceanPlan,setOceanPlan]=useState(null);
  const consumeNote = useCallback(() => setPendingNote(null), []);

  useEffect(() => {
    if (!chat.ready) return;
    let alive = true;
    const check = () =>
      api("/health")
        .then((data) => {
          if (alive) setHealth(data);
        })
        .catch(() => {
          if (alive)
            setHealth({ matlab_available: false, gateway_online: false });
        });
    check();
    const timer = setInterval(check, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [refresh, chat.ready]);
  useEffect(() => {
    const open = () => {
      setPage("settings");
      setSidebarOpen(false);
    };
    const changed = () => {
      void chat.reloadConfig();
      setRefresh((value) => value + 1);
    };
    window.addEventListener("ocean-open-settings", open);
    window.addEventListener("ocean-model-config-changed", changed);
    return () => {
      window.removeEventListener("ocean-open-settings", open);
      window.removeEventListener("ocean-model-config-changed", changed);
    };
  }, [chat.reloadConfig]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 7000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") {
        setImage(null);
        setSidebarOpen(false);
      }
      if (event.altKey && /^[1-8]$/.test(event.key)) {
        event.preventDefault();
        setPage(
          [...pages.map((item) => item[0]), "settings"][Number(event.key) - 1],
        );
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const title = pages.find((item) => item[0] === page)?.[1] || "模型与环境";
  const navigate = useCallback((id) => {
    setPage(id);
    setSidebarOpen(false);
  }, []);
  const openChatSettings = useCallback(
    () => navigate("settings"),
    [navigate],
  );
  const openChatKnowledge = useCallback(
    (id) => {
      setInitialKnowledge({ id, request: Date.now() });
      navigate("graph");
    },
    [navigate],
  );
  const openSimulationDraft = useCallback(
    (value) => {
      if(value?.draft_plan){const p=value.draft_plan;setOceanPlan({...p,frequencies_hz:p.frequencies_hz.join(', '),source_depths_m:p.source_depths_m.join(', ')})}else setOceanPlan(null);
      setInitialSimulation({
        draft: value?.draft_plan ? value : null,
        node_id: value?.node_id || null,
        request: Date.now(),
        apply: !!value?.draft_plan,
      });
      navigate("simulation");
    },
    [navigate],
  );
  useEffect(() => {
    const collect = (event) => {
      if (event.detail && typeof event.detail.body === "string") {
        setPendingNote(event.detail);
        navigate("workspace");
      }
    };
    window.addEventListener("ocean-save-research-note", collect);
    return () =>
      window.removeEventListener("ocean-save-research-note", collect);
  }, [navigate]);
  const connected = !!health?.matlab_available;

  return (
    <div
      data-page={page}
      className={"app workbench-app" + (sidebarOpen ? " sidebar-open" : "")}
    >
      <a className="skip-link" href="#workspace-content">
        跳到工作区域
      </a>
      {sidebarOpen && (
        <button
          className="sidebar-scrim"
          aria-label="关闭导航"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside className="sidebar" aria-label="主导航">
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            navigate("graph");
          }}
        >
          <span className="brand-icon">
            <Waves size={23} />
          </span>
          <div>
            海洋声学<span>课程工作台</span>
          </div>
        </a>
        <OceanProfile />
        <div className="side-label">研究与学习</div>
        <nav>
          {pages.map(([id, label, Icon], index) => (
            <button
              key={id}
              className={page === id ? "nav-item active" : "nav-item"}
              aria-current={page === id ? "page" : undefined}
              title={"Alt + " + (index + 1)}
              onClick={() => navigate(id)}
            >
              <Icon size={17} />
              <span>{label}</span>
              {id === "graph" && (
                <span className="nav-count">
                  {health?.knowledge_cards || 46}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <FolderCode size={16} />
          <div>
            当前课程项目<span>Munk 深海声道 / KRAKEN</span>
          </div>
        </div>
        <div className="side-bottom">
          <button
            className={page === "settings" ? "nav-item active" : "nav-item"}
            title="Alt + 7"
            onClick={() => navigate("settings")}
          >
            <Settings2 size={17} />
            <span>模型与环境</span>
          </button>
          <a
            className="repository-link"
            href="https://github.com/Weijifen666/ocean-acoustic-workbench"
            target="_blank"
            rel="noreferrer"
          >
            <GitBranch size={15} />
            项目源码
            <ExternalLink size={12} />
          </a>
          <div className="team">
            四人小组
            <br />
            高嘉豪 · 周子涵 · 刘继洲 · 李杰
          </div>
          <AccountBadge onOpen={() => navigate("workspace")} />
          <div className="course-purpose">仅用于课程作业 · 无商业用途</div>
        </div>
      </aside>
      <div className="main">
        <header className="workspace-header">
          <div className="workspace-header-left">
            <button
              className="mobile-menu"
              aria-label="打开导航菜单"
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen((open) => !open)}
            >
              <SlidersHorizontal size={19} />
            </button>
            <div className="breadcrumb">
              海洋声学工作台
              <ChevronRight size={14} />
              <strong>{title}</strong>
            </div>
          </div>
          <div className="header-status">
            <span
              title={
                connected
                  ? "共享计算节点已连接"
                  : "节点离线时仍可浏览云端课程图谱"
              }
            >
              <i className={connected ? "green" : "orange"} />
              {health === null
                ? "正在检测计算节点"
                : connected
                  ? "MATLAB 已连接"
                  : "计算节点离线"}
            </span>
          </div>
        </header>
        <main id="workspace-content" tabIndex={-1}><PageErrorBoundary key={page}>
          {!chat.ready && page !== "chat" && (
            <section className="panel visitor-loading">
              <Loader2 className="spin" size={20} />
              <h2>正在准备课程空间</h2>
              <p>{chat.loadError || "载入你的模型配置与对话。"}</p>
              {chat.loadError && (
                <Button onClick={() => chat.reloadConfig()}>重新载入</Button>
              )}
            </section>
          )}
          {chat.ready && page === "graph" && (
            <GraphExplorer
              setImage={setImage}
              notify={setToast}
              initialKnowledge={initialKnowledge}
              onAsk={(node) => {
                setResearchDraft({id:crypto.randomUUID(),text:`请解释知识图谱中的“${node.label}”，结合公式、适用条件和相关知识点，并给出资料出处。`});
                navigate("chat");
              }}
              onSimulation={(node) => openSimulationDraft({ node_id: node.id })}
            />
          )}
          {page === "chat" && (
            <DialogueWorkbench
              health={health}
              notify={setToast}
              openSettings={openChatSettings}
              onSimulation={openSimulationDraft}
              onKnowledge={openChatKnowledge}
              draft={researchDraft}
            />
          )}
          {page === "ocean" && <div className="studio-page"><OceanData notify={setToast} onSimulate={draft=>{setOceanPlan(draft);navigate("simulation")}}/></div>}
          {page === "simulation" && (
            <div className="studio-page"><Simulation
              onAsk={text=>{setResearchDraft({id:crypto.randomUUID(),text});navigate("chat")}}
              notify={setToast}
              initialEnvironment={oceanPlan}
              onSubmit={(id) => {
                setActiveJob(id);
                navigate("jobs");
              }}
            /></div>
          )}
          {chat.ready && page === "project" && <Project notify={setToast} />}
          {page === "jobs" && (
            <div className="studio-page"><Jobs
              onResearch={()=>{setResearchDraft({id:crypto.randomUUID(),text:'请独立完成一个研究任务，查资料、运行脚本、验证并保存报告。研究目标：'});navigate("chat")}}
              onImportChat={task=>{setResearchDraft(taskChatDraft(task));navigate("chat");setToast("任务数据已导入，编辑问题后发送即可分析")}}
              notify={setToast}
              activeJob={activeJob}
              setActiveJob={setActiveJob}
              openSim={() => navigate("simulation")}
              setImage={setImage}
            /></div>
          )}
          {chat.ready && page === "workspace" && (
            <ResearchWorkspace
              notify={setToast}
              pendingNote={pendingNote}
              onConsumed={consumeNote}
            />
          )}
          {chat.ready && page === "settings" && (
            <Config
              notify={setToast}
              onSaved={() => {
                void chat.reloadConfig();
                setRefresh((value) => value + 1);
              }}
            />
          )}
        </PageErrorBoundary></main>
        <footer className="workspace-statusbar">
          <span>
            <i className={connected ? "green" : "orange"} />
            {health === null
              ? "正在检测计算节点"
              : connected
                ? "共享 MATLAB 计算节点在线"
                : "课程图谱可用 · 计算节点待连接"}
          </span>
          <span>
            课程空间<span className="status-divider">|</span>v0.7
          </span>
        </footer>
      </div>
      {toast && (
        <div className="toast" role="status">
          <AlertCircle size={17} />
          {toast}
          <button aria-label="关闭提示" onClick={() => setToast("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {image && (
        <div className="modal-backdrop" onClick={() => setImage(null)}>
          <div
            className="image-modal"
            role="dialog"
            aria-modal="true"
            aria-label={image.caption}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-title">
              {image.caption}
              <button
                aria-label="关闭图片"
                autoFocus
                onClick={() => setImage(null)}
              >
                <X />
              </button>
            </div>
            <img src={image.url} alt={image.caption} />
            {image.source_url && (
              <a target="_blank" rel="noreferrer" href={image.source_url}>
                查看原始来源 <ExternalLink size={14} />
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
function PageTitle({ title, description, children }) {
  return (
    <div className="page-title">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children && <div className="page-actions">{children}</div>}
    </div>
  );
}
function Project({ notify }) {
  const [data, setData] = useState(null),
    [file, setFile] = useState(null),
    [q, setQ] = useState(""),
    [source, setSource] = useState("all");
  function refresh() {
    api("/project/files")
      .then(setData)
      .catch((e) => notify(e.message));
  }
  useEffect(refresh, []);
  const files = (data?.files || []).filter(f =>
    (source === 'all' || f.group === source) &&
    (f.label || f.path).toLowerCase().includes(q.trim().toLowerCase()));
  async function open(path) {
    try {
      setFile(await api("/project/file?path=" + encodeURIComponent(path)));
    } catch (e) {
      notify(e.message);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="PROJECT FILES"
        title="项目文件"
        description="按用途浏览程序、模型输入、计算结果和说明文件。"
      ><Button onClick={refresh}><RotateCcw size={14}/>刷新文件</Button></PageTitle>
      <div className="project-root">
        <FolderCode size={16} />
        {!data ? "正在读取项目目录…" : source === 'all' ? "工作台代码 · 示例项目 · 任务目录" : data.roots?.[source] || data.root}
        <span>只读浏览</span>
      </div>
      <div className="project-layout">
        <aside className="panel project-file-sidebar">
          <label className="project-source-filter">文件来源
            <select aria-label="文件来源" value={source} onChange={e=>setSource(e.target.value)}>
              <option value="all">全部来源</option>
              {data?.groups?.map(group=><option value={group.id} key={group.id}>{group.name}</option>)}
            </select>
          </label>
          <label className="search">
            <Search size={15} />
            <input
              aria-label="筛选文件"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索文件名或任务编号"
            />
          </label>
          <p className="project-file-count">{files.length} 个文件 · 点击分类展开</p>
          <div className="file-list categorized-files">
            {projectCategories.map(([category,title])=>{
              const entries=files.filter(f=>projectCategory(f)===category);
              if(!entries.length)return null;
              return <details className="project-file-category" key={category+source+q.trim()} open={q.trim()?true:undefined}>
                <summary>{title}<span>{entries.length}</span></summary>
                {entries.map((f) => (
                <button
                  key={f.path}
                  className={file?.path === f.path ? "selected" : ""}
                  onClick={() => open(f.path)}
                >
                  <FileText size={15} />
                  <span>
                    {f.label || f.path}
                    <small>{(f.size / 1024).toFixed(1)} KB</small>
                  </span>
                </button>
              ))}</details>;
            })}
            {data && !files.length && <p className="project-no-files">没有符合条件的文件</p>}
          </div>
        </aside>
        <section className="panel editor">
          <div className="panel-heading">
            {file?.path || "选择一个项目文件"}
            <span>UTF-8</span>
          </div>
          {file?.kind==="image" ? <img src={file.url} alt={file.path} style={{maxWidth:"100%"}}/> : file?.kind==="raw" ? <a className="button" href={file.url}>下载原始数据文件</a> : file ? (
            <>
              <pre className="code">
                {file.content.split("\n").map((line, i) => (
                  <div key={i}>
                    <span className="line-num">{i + 1}</span>
                    {line || " "}
                  </div>
                ))}
              </pre>
              <div className="editor-foot">
                SHA-256 {file.sha256.slice(0, 20)}… · 本机授权文件 · 只读
              </div>
            </>
          ) : (
            <div className="empty">
              <FolderCode size={38} />
              <p>点击左侧文件查看内容</p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
function Config({ notify, onSaved }) {
  const [cfg, setCfg] = useState(null),
    [checks, setChecks] = useState(null),
    [busy, setBusy] = useState(false),
    [resources, setResources] = useState([]);
  useEffect(() => {
    api("/config")
      .then(setCfg)
      .catch((e) => notify(e.message));
    api("/sources")
      .then(setResources)
      .catch((e) => notify(e.message));
    api("/environment/check", { method: "POST" })
      .then(setChecks)
      .catch((e) => notify(e.message));
  }, []);
  async function save() {
    setBusy(true);
    try {
      await api("/config", { method: "PUT", body: JSON.stringify(cfg) });
      notify("已保存当前访客的模型配置");
      onSaved();
      setCfg(await api("/config"));
      setChecks(await api("/environment/check", { method: "POST" }));
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (!cfg)
    return (
      <div className="empty">
        <Loader2 className="spin" />
      </div>
    );
  const input = (key) => (e) =>
    setCfg((c) => ({ ...c, [key]: e.target.value }));
  return (
    <>
      <PageTitle
        eyebrow="ENVIRONMENT"
        title="模型与环境"
        description="填写你自己的模型密钥；MATLAB 由共享计算节点执行。"
      >
        <Button variant="primary" disabled={busy} onClick={save}>
          <Save size={15} />
          保存配置
        </Button>
      </PageTitle>
      <div className="settings-layout public-settings">
        {!cfg.public_mode && (
          <section className="panel settings-panel">
            <div className="panel-heading">
              <span>
                <Terminal size={17} />
                本地计算环境
              </span>
              <span className="tag">Windows</span>
            </div>
            <Field label="MATLAB 可执行路径">
              <input value={cfg.matlab_path} onChange={input("matlab_path")} />
            </Field>
            <Field label="AT 工具包目录">
              <input
                value={cfg.toolbox_path}
                onChange={input("toolbox_path")}
              />
            </Field>
            <Field label="授权项目目录">
              <input
                value={cfg.project_path}
                onChange={input("project_path")}
              />
            </Field>
            <Field label="单任务超时" unit="秒">
              <input
                type="number"
                value={cfg.timeout_seconds}
                onChange={input("timeout_seconds")}
              />
            </Field>
            <Button
              onClick={async () => {
                try {
                  setChecks(
                    await api("/environment/check", { method: "POST" }),
                  );
                  notify("环境检查完成");
                } catch (e) {
                  notify(e.message);
                }
              }}
            >
              <CheckCircle2 size={15} />
              检查运行环境
            </Button>
          </section>
        )}
        <ModelPanel
          cfg={cfg}
          setCfg={setCfg}
          onSave={save}
          busy={busy}
          notify={notify}
        />
      </div>
      {checks && (
        <section className="panel environment-checks">
          <div className="panel-heading">环境检查结果</div>
          <div>
            {checks.checks.map((c) => (
              <div className="check-item" key={c.name}>
                {c.ok ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}
                <div>
                  <strong>{c.name}</strong>
                  <small>{c.detail}</small>
                </div>
                <span className={c.ok ? "ok" : "pending"}>
                  {c.ok ? "通过" : "待配置"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="panel resource-panel">
        <div className="panel-heading">
          资料来源与入库状态<span>{resources.length} 份来源</span>
        </div>
        <div className="resource-scroll">
          <table>
            <thead>
              <tr>
                <th>编号</th>
                <th>来源文件</th>
                <th>资料状态</th>
                <th>知识关联</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {resources.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>
                    {s.name}
                    <small>{s.reading_scope}</small>
                  </td>
                  <td>
                    {s.duplicate_of
                      ? "重复 " + s.duplicate_of
                      : s.extraction_state === "needs_ocr"
                        ? "扫描版 · 待 OCR"
                        : s.available
                          ? "PDF 可预览"
                          : "元数据已登记"}
                  </td>
                  <td>{s.index_status}</td>
                  <td>
                    {s.available && (
                      <a
                        href={"/api/source/" + s.id}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <ExternalLink size={15} />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
createRoot(document.getElementById("root")).render(
  <ChatProvider>
    <AccountProvider>
      <App />
    </AccountProvider>
  </ChatProvider>,
);
