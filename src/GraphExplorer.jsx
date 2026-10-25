import React, { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import {
  Network,
  Search,
  ChevronRight,
  ChevronDown,
  BookOpen,
  Maximize2,
  Minimize2,
  Plus,
  Minus,
  RotateCcw,
  X,
  Star,
  Check,
  ArrowUpRight,
  ArrowRight,
  Route,
  Layers,
  Sun,
  Moon,
  SlidersHorizontal,
  MessageSquare,
  Play,
  Link2,
  Download,
  FileText,
  GraduationCap,
} from "lucide-react";
import "./graph.css";
import OceanBanner from "./OceanBanner";
const groups = {
  hierarchy: "父子关系",
  prerequisite: "建议先学",
  related: "概念关联",
};
const get = async (path, options) => {
  const r = await fetch("/api" + path, options);
  if (!r.ok) {
    const e = await r.json();
    throw Error(e.detail || "请求失败");
  }
  return r.json();
};
function useStored(key) {
  const [value, setValue] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(key) || "[]");
    } catch {
      return [];
    }
  });
  const toggle = (id) =>
    setValue((old) => {
      const next = old.includes(id)
        ? old.filter((x) => x !== id)
        : [...old, id];
      localStorage.setItem(key, JSON.stringify(next));
      return next;
    });
  return [value, toggle];
}
export default function GraphExplorer({
  setImage,
  notify,
  onAsk,
  onSimulation,
  initialKnowledge,
}) {
  const [graph, setGraph] = useState(null),
    [tab, setTab] = useState("graph"),
    [view, setView] = useState("overview"),
    [chapter, setChapter] = useState("basics"),
    [expanded, setExpanded] = useState(["basics"]),
    [selected, setSelected] = useState(null),
    [detailTab, setDetailTab] = useState("overview"),
    [selectedEdge, setSelectedEdge] = useState(null),
    [search, setSearch] = useState(""),
    [layout, setLayout] = useState("radial"),
    [relationGroups, setRelationGroups] = useState(["hierarchy", "related"]),
    [neighborsOnly, setNeighborsOnly] = useState(false),
    [theme, setTheme] = useState("light"),
    [fullscreen, setFullscreen] = useState(false),
    [onlyStar, setOnlyStar] = useState(false),
    [pathId, setPathId] = useState("first"),
    [source, setSource] = useState("sound_speed_profile"),
    [target, setTarget] = useState("transmission_loss"),
    [connection, setConnection] = useState(null),
    [showPath, setShowPath] = useState(false),
    [sources, setSources] = useState([]);
  const [knowledgeStatus, setKnowledgeStatus] = useState(null);
  const [directoryVisible, setDirectoryVisible] = useState(
    () => window.innerWidth >= 800,
  );
  const [read, toggleRead] = useStored("ocean:read:v2"),
    [stars, toggleStar] = useStored("ocean:stars:v2");
  const graphRef = useRef(null);
  useEffect(() => {
    get("/graph")
      .then((data) => {
        const palette = [
          "#376f94",
          "#357c74",
          "#766290",
          "#997948",
          "#916075",
          "#587b90",
        ];
        const colors = Object.fromEntries(
          data.chapters.map((c, i) => [c.id, palette[i % palette.length]]),
        );
        setGraph({
          ...data,
          chapters: data.chapters.map((c) => ({ ...c, color: colors[c.id] })),
          nodes: data.nodes.map((n) => ({
            ...n,
            color: colors[n.chapter || n.id] || "#526d85",
          })),
        });
      })
      .catch((e) => notify(e.message));
    get("/sources")
      .then(setSources)
      .catch((e) => notify(e.message));
    get("/knowledge/status")
      .then(setKnowledgeStatus)
      .catch(() => {});
  }, []);
  useEffect(() => {
    const f = (e) => {
      if (e.key === "Escape") {
        setFullscreen(false);
        setSelected(null);
      }
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, []);
  const knowledge = graph?.nodes.filter((n) => n.kind === "knowledge") || [],
    nodesById = useMemo(
      () => Object.fromEntries((graph?.nodes || []).map((n) => [n.id, n])),
      [graph],
    );
  const matches = knowledge.filter(
    (n) =>
      (!onlyStar || stars.includes(n.id)) &&
      (!search ||
        [n.label, n.id, n.overview, ...n.key_points, ...n.tags]
          .join(" ")
          .toLowerCase()
          .includes(search.toLowerCase())),
  );
  const node = nodesById[selected],
    unit = graph?.chapters.find((c) => c.id === chapter),
    relations =
      graph?.edges.filter(
        (e) =>
          e.group !== "hierarchy" && [e.source, e.target].includes(selected),
      ) || [];
  function choose(id) {
    const n = nodesById[id];
    if (!n) return;
    setSelectedEdge(null);
    setDetailTab("overview");
    if (n.kind === "chapter") {
      setChapter(id);
      setView("chapter");
      setSelected(null);
      setExpanded((old) => (old.includes(id) ? old : [...old, id]));
      return;
    }
    if (n.kind === "course") {
      setView("overview");
      setSelected(null);
      return;
    }
    setSelected(id);
    setChapter(n.chapter);
    setExpanded((old) => (old.includes(n.chapter) ? old : [...old, n.chapter]));
    if (view === "overview") setView("chapter");
    setTab("graph");
  }
  useEffect(() => {
    if (graph && initialKnowledge?.id) choose(initialKnowledge.id);
  }, [graph, initialKnowledge]);
  function groupToggle(group) {
    setRelationGroups((old) =>
      old.includes(group) ? old.filter((g) => g !== group) : [...old, group],
    );
  }
  async function findConnection() {
    try {
      const r = await get("/graph/path?source=" + source + "&target=" + target);
      setConnection(r);
      if (r.nodes.length) {
        setView("all");
        setSelected(null);
        setRelationGroups(["related"]);
        setNeighborsOnly(false);
      } else notify("当前关系中未找到连接");
    } catch (e) {
      notify(e.message);
    }
  }
  if (!graph) return <div className="empty panel">正在载入课程知识图谱…</div>;
  return (
    <section
      className={
        "course-explorer " +
        theme +
        (fullscreen ? " graph-fullscreen" : "") +
        (node?.kind === "knowledge" ? " with-detail" : "") +
        (!directoryVisible ? " hidden-directory" : "")
      }
    >
      <OceanBanner
        chapters={graph.chapters.length}
        nodes={knowledge.length}
        relations={graph.edge_count ?? graph.edges?.length ?? null}
        read={
          read.filter((id) => knowledge.some((node) => node.id === id)).length
        }
      />
      <div className="course-tabs">
        <div>
          {[
            ["graph", "知识图谱", Network],
            ["map", "学习地图", Route],
            ["resources", "学习资源", BookOpen],
          ].map(([id, title, Icon]) => (
            <button
              key={id}
              className={tab === id ? "active" : ""}
              onClick={() => {
                setTab(id);
                setSelected(null);
              }}
            >
              <Icon size={16} />
              {title}
            </button>
          ))}
        </div>
        <div className="course-top-tools">
          <button
            title="显示或隐藏课程目录"
            aria-label="显示或隐藏课程目录"
            aria-expanded={directoryVisible}
            onClick={() => setDirectoryVisible((value) => !value)}
          >
            <Layers size={16} />
          </button>
          <button
            title={theme === "dark" ? "切换浅色" : "切换深色"}
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button
            title={fullscreen ? "退出全屏图谱" : "全屏图谱"}
            onClick={() => setFullscreen((x) => !x)}
          >
            {fullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </div>
      <div className="course-body">
        <aside className="course-directory">
          <div className="directory-title">
            <strong>课程目录</strong>
            <button
              title="只看收藏"
              className={onlyStar ? "active" : ""}
              onClick={() => setOnlyStar((x) => !x)}
            >
              <Star size={16} fill={onlyStar ? "currentColor" : "none"} />
            </button>
          </div>
          <label className="course-search">
            <Search size={15} />
            <input
              aria-label="搜索课程知识点"
              placeholder="搜索知识点、术语"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button aria-label="清空搜索" onClick={() => setSearch("")}>
                <X size={13} />
              </button>
            )}
          </label>
          <button
            className={
              "directory-home " +
              (view === "overview" && tab === "graph" ? "active" : "")
            }
            onClick={() => {
              setView("overview");
              setTab("graph");
              setSelected(null);
              setConnection(null);
            }}
          >
            <Network size={16} />
            <span>课程总览</span>
            <small>{knowledge.length}</small>
          </button>
          {(search || onlyStar) && (
            <div className="search-count">
              {matches.length} 个匹配知识点{onlyStar ? " · 已收藏" : ""}
            </div>
          )}
          <div className="directory-tree">
            {graph.chapters.map((c) => {
              const items = matches.filter((n) => n.chapter === c.id),
                all = knowledge.filter((n) => n.chapter === c.id),
                open = expanded.includes(c.id) || !!search || onlyStar;
              return (
                <div className="tree-unit" key={c.id}>
                  {((!search && !onlyStar) || items.length > 0) && (
                    <>
                      <div
                        className={
                          "unit-heading " +
                          (chapter === c.id && view === "chapter"
                            ? "current"
                            : "")
                        }
                      >
                        <button
                          aria-label={(open ? "收起" : "展开") + c.label}
                          onClick={() =>
                            setExpanded((old) =>
                              old.includes(c.id)
                                ? old.filter((x) => x !== c.id)
                                : [...old, c.id],
                            )
                          }
                        >
                          {open ? (
                            <ChevronDown size={13} />
                          ) : (
                            <ChevronRight size={13} />
                          )}
                        </button>
                        <button
                          className="unit-name"
                          onClick={() => {
                            choose(c.id);
                            setTab("graph");
                          }}
                        >
                          <i style={{ background: c.color }} />
                          <span>
                            {String(c.number).padStart(2, "0")} {c.label}
                          </span>
                          <small>{all.length}</small>
                        </button>
                      </div>
                      {open && (
                        <div className="unit-children">
                          {items.map((n) => (
                            <button
                              key={n.id}
                              className={selected === n.id ? "current" : ""}
                              onClick={() => choose(n.id)}
                            >
                              <span
                                className={
                                  "read-marker " +
                                  (read.includes(n.id) ? "read" : "")
                                }
                                style={{ color: c.color }}
                              >
                                {read.includes(n.id) ? (
                                  <Check size={10} />
                                ) : null}
                              </span>
                              <span>{n.label}</span>
                              {stars.includes(n.id) && <Star size={10} />}
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
          <div className="directory-progress">
            <div>
              <span>阅读记录</span>
              <strong>
                {Math.round(
                  (read.filter((id) => knowledge.some((n) => n.id === id))
                    .length /
                    knowledge.length) *
                    100,
                )}
                %
              </strong>
            </div>
            <div className="progress-track">
              <i
                style={{ width: (read.length / knowledge.length) * 100 + "%" }}
              />
            </div>
            <small>点击知识点后可标记已读</small>
          </div>
        </aside>
        <div className="course-workspace">
          {tab === "graph" ? (
            <>
              <div className="graph-controlbar">
                <div className="view-switch">
                  {[
                    ["overview", "单元目录"],
                    ["all", "全部关系"],
                    ["chapter", "单元关系"],
                  ].map(([id, title]) => (
                    <button
                      key={id}
                      className={view === id ? "active" : ""}
                      onClick={() => {
                        setView(id);
                        setSelected(null);
                        setConnection(null);
                      }}
                    >
                      {title}
                    </button>
                  ))}
                </div>
                <div className="graph-view-options">
                  {view === "chapter" && (
                    <select
                      aria-label="选择课程单元"
                      value={chapter}
                      onChange={(e) => {
                        setChapter(e.target.value);
                        setSelected(null);
                      }}
                    >
                      {graph.chapters.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  )}
                  {view !== "overview" && (
                    <select
                      aria-label="图谱布局"
                      value={layout}
                      onChange={(e) => setLayout(e.target.value)}
                    >
                      <option value="radial">放射布局</option>
                      <option value="tree">层级布局</option>
                      <option value="circle">环形布局</option>
                    </select>
                  )}
                  <button
                    title="查找知识点间的关联路径"
                    className={showPath ? "active" : ""}
                    onClick={() => setShowPath((x) => !x)}
                  >
                    <Link2 size={15} />
                    <span>关联路径</span>
                  </button>
                </div>
              </div>
              {showPath && (
                <div className="connection-finder">
                  <select
                    aria-label="路径起点"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                  >
                    {knowledge.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.label}
                      </option>
                    ))}
                  </select>
                  <ArrowRight size={14} />
                  <select
                    aria-label="路径终点"
                    value={target}
                    onChange={(e) => setTarget(e.target.value)}
                  >
                    {knowledge.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.label}
                      </option>
                    ))}
                  </select>
                  <button onClick={findConnection}>查找关联</button>
                  {connection?.nodes.length > 0 && (
                    <div className="connection-result">
                      {connection.nodes.map((id, i) => (
                        <React.Fragment key={id}>
                          {i > 0 && <ChevronRight size={12} />}
                          <button onClick={() => choose(id)}>
                            {nodesById[id].label}
                          </button>
                        </React.Fragment>
                      ))}
                      <small>{connection.direction_note}</small>
                    </div>
                  )}
                </div>
              )}
              <div className="graph-stage">
                {view === "overview" ? (
                  <CourseUniverse
                    chapters={graph.chapters}
                    knowledge={knowledge}
                    read={read}
                    choose={choose}
                  />
                ) : (
                  <>
                    <div className="canvas-heading">
                      <span
                        style={{
                          color: view === "chapter" ? unit.color : undefined,
                        }}
                      >
                        {view === "chapter"
                          ? `${String(unit.number).padStart(2, "0")} · ${unit.label}`
                          : "海洋声学 · 全部课程知识"}
                      </span>
                      <small>
                        {view === "chapter"
                          ? knowledge.filter((n) => n.chapter === chapter)
                              .length
                          : knowledge.length}{" "}
                        个知识点 · 点击节点查看详情
                      </small>
                    </div>
                    <KnowledgeCanvas
                      theme={theme}
                      graph={graph}
                      chapter={chapter}
                      view={view}
                      layout={layout}
                      selected={selected}
                      groups={relationGroups}
                      search={search}
                      neighborsOnly={neighborsOnly}
                      read={read}
                      connection={connection}
                      choose={choose}
                      onEdge={(id) => {
                        const e = graph.edges.find((x) => x.id === id);
                        setSelected(e.target);
                        setSelectedEdge(id);
                        setDetailTab("relations");
                      }}
                      graphRef={graphRef}
                    />
                    <div className="canvas-zoom">
                      <button
                        aria-label="放大图谱"
                        onClick={() =>
                          graphRef.current?.zoom(graphRef.current.zoom() * 1.2)
                        }
                      >
                        <Plus size={17} />
                      </button>
                      <button
                        aria-label="缩小图谱"
                        onClick={() =>
                          graphRef.current?.zoom(graphRef.current.zoom() / 1.2)
                        }
                      >
                        <Minus size={17} />
                      </button>
                      <button
                        aria-label="重置图谱"
                        onClick={() => graphRef.current?.fit(undefined, 55)}
                      >
                        <RotateCcw size={16} />
                      </button>
                    </div>
                  </>
                )}
                {view !== "overview" && (
                  <div className="graph-status-line">
                    <i />
                    拖动节点或画布 · 滚轮缩放 · 点击节点查阅图文
                  </div>
                )}
              </div>
              {view !== "overview" && (
                <div className="relation-legend">
                  {Object.entries(groups).map(([id, title]) => (
                    <button
                      className={relationGroups.includes(id) ? "checked" : ""}
                      key={id}
                      onClick={() => groupToggle(id)}
                    >
                      <span className={"legend-line " + id} />
                      <span>{title}</span>
                      <small>
                        {graph.edges.filter((e) => e.group === id).length}
                      </small>
                    </button>
                  ))}
                  <label>
                    <input
                      type="checkbox"
                      disabled={!selected}
                      checked={neighborsOnly}
                      onChange={(e) => setNeighborsOnly(e.target.checked)}
                    />
                    只看当前关联
                  </label>
                </div>
              )}
            </>
          ) : tab === "map" ? (
            <div className="learning-map">
              <div className="map-heading">
                <div>
                  <h2>从知识到一次完整仿真</h2>
                  <p>按建议顺序阅读，或点击任意知识点查看详情。</p>
                </div>
                <select
                  aria-label="选择学习路径"
                  value={pathId}
                  onChange={(e) => setPathId(e.target.value)}
                >
                  {graph.learning_paths.map((p) => (
                    <option value={p.id} key={p.id}>
                      {p.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="path-intro">
                <Route size={18} />
                <div>
                  <strong>
                    {graph.learning_paths.find((p) => p.id === pathId).title}
                  </strong>
                  <span>
                    {
                      graph.learning_paths.find((p) => p.id === pathId)
                        .description
                    }
                  </span>
                </div>
                <small>建议路径</small>
              </div>
              <div className="learning-steps">
                {graph.learning_paths
                  .find((p) => p.id === pathId)
                  .nodes.map((id, i) => {
                    const n = nodesById[id];
                    return (
                      <button
                        key={id}
                        className={
                          "learning-step " + (read.includes(id) ? "done" : "")
                        }
                        style={{ "--node-color": n.color }}
                        onClick={() => choose(id)}
                      >
                        <span className="step-number">
                          {read.includes(id) ? (
                            <Check size={18} />
                          ) : (
                            String(i + 1).padStart(2, "0")
                          )}
                        </span>
                        <div>
                          <small>
                            {
                              graph.chapters.find((c) => c.id === n.chapter)
                                .label
                            }
                          </small>
                          <h3>{n.label}</h3>
                          <p>{n.overview}</p>
                          <span>
                            {read.includes(id) ? "已读" : "查看知识"}
                            <ArrowUpRight size={13} />
                          </span>
                        </div>
                      </button>
                    );
                  })}
              </div>
              <div className="unit-map-heading">
                全部课程单元 <small>每个单元可独立进入</small>
              </div>
              <div className="unit-map-grid">
                {graph.chapters.map((c) => {
                  const items = knowledge.filter((n) => n.chapter === c.id);
                  return (
                    <div
                      className="unit-map-card"
                      key={c.id}
                      style={{ "--unit-color": c.color }}
                    >
                      <div>
                        <small>{String(c.number).padStart(2, "0")}</small>
                        <strong>{c.label}</strong>
                        <span>{items.length} 个知识点</span>
                      </div>
                      {items.map((n) => (
                        <button key={n.id} onClick={() => choose(n.id)}>
                          <i className={read.includes(n.id) ? "done" : ""} />
                          {n.label}
                          <ChevronRight size={12} />
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="course-resources">
              <KnowledgeIndexStatus
                status={knowledgeStatus}
                cards={knowledge.length}
              />
              <PublicOceanResources status={knowledgeStatus?.public_ocean} />
              <div className="map-heading">
                <div>
                  <h2>学习资料与知识关联</h2>
                  <p>
                    图谱提供知识点关联及教材原页片段；完整资料使用课程资料包。
                  </p>
                </div>
              </div>
              <div className="resource-card-grid">
                {sources
                  .filter((s) => !s.duplicate_of)
                  .map((s) => {
                    const linked = knowledge.filter((n) =>
                      n.references.some((r) => r.source_id === s.id),
                    );
                    const sourceCoverage =
                      knowledgeStatus?.source_coverage?.find(
                        (row) => row.source_id === s.id,
                      );
                    return (
                      <div className="course-resource-card" key={s.id}>
                        <div className="resource-cover">
                          <BookOpen size={32} />
                          <span>{s.id}</span>
                        </div>
                        <div>
                          <small>
                            {s.type === ".pdf"
                              ? "PDF 教材 / 报告"
                              : s.type === ".mp4"
                                ? "视频教程"
                                : "计算工具包"}
                          </small>
                          <h3>{s.name}</h3>
                          <p>
                            {linked.length
                              ? `已关联 ${linked.length} 个知识点`
                              : "资料已登记，知识内容待进一步整理"}
                          </p>
                          {sourceCoverage && (
                            <p className="resource-indexed">
                              已处理 {sourceCoverage.processed_pages} 页 ·
                              已索引 {sourceCoverage.indexed_pages} 页 ·{" "}
                              {sourceCoverage.chunks} 个片段
                              {sourceCoverage.failed_or_needs_ocr_pages > 0 && (
                                <>
                                  {" "}
                                  · {
                                    sourceCoverage.failed_or_needs_ocr_pages
                                  }{" "}
                                  页待核查
                                </>
                              )}
                            </p>
                          )}
                          <div className="resource-node-links">
                            {linked.slice(0, 3).map((n) => (
                              <button key={n.id} onClick={() => choose(n.id)}>
                                {n.label}
                              </button>
                            ))}
                          </div>
                          {s.available ? (
                            <a
                              href={"/api/source/" + s.id}
                              target="_blank"
                              rel="noreferrer"
                            >
                              打开原始 PDF
                              <ArrowUpRight size={14} />
                            </a>
                          ) : (
                            <span className="resource-pending">
                              {s.id === "S20"
                                ? "AT 已导入计算节点"
                                : sourceCoverage?.indexed_pages > 0
                                  ? "正文已进入私有检索索引 · 回答可引用原页"
                                  : s.type === ".pdf" && linked.length > 0
                                    ? "提供知识点对应原页片段"
                                    : "元数据已登记 · 内容未入库"}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
        {node?.kind === "knowledge" && (
          <div className="knowledge-drawer">
            <div className="drawer-header">
              <div>
                <span style={{ color: node.color }}>
                  {graph.chapters.find((c) => c.id === node.chapter).label}
                </span>
                <h2>{node.label}</h2>
              </div>
              <button
                aria-label="关闭知识详情"
                onClick={() => {
                  setSelected(null);
                  setSelectedEdge(null);
                }}
              >
                <X size={19} />
              </button>
            </div>
            <div className="knowledge-tags">
              {node.tags.map((t) => (
                <span key={t}>{t}</span>
              ))}
              {node.formula && <span>含公式</span>}
              {node.simulation && <span>可关联仿真</span>}
            </div>
            <div className="drawer-tabs">
              {[
                ["overview", "知识讲解"],
                ["relations", "关联知识"],
                ["sources", "图片与来源"],
              ].map(([id, title]) => (
                <button
                  key={id}
                  className={detailTab === id ? "active" : ""}
                  onClick={() => setDetailTab(id)}
                >
                  {title}
                </button>
              ))}
            </div>
            <div className="drawer-scroll">
              {detailTab === "overview" ? (
                <>
                  <p className="knowledge-overview">{node.overview}</p>
                  {node.diagram && (
                    <button
                      className="knowledge-diagram"
                      onClick={() => setImage(node.images[0])}
                    >
                      <img
                        src={node.images[0].url}
                        alt={node.label + "原理示意"}
                      />
                      <span>
                        查看完整示意图 <Maximize2 size={12} />
                      </span>
                    </button>
                  )}
                  {node.formula && (
                    <div className="knowledge-formula">
                      <small>核心关系</small>
                      <div>{node.formula}</div>
                    </div>
                  )}
                  <h3>理解要点</h3>
                  <ol className="knowledge-points">
                    {node.key_points.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ol>
                  {node.conditions && (
                    <div className="knowledge-note">
                      <strong>适用条件</strong>
                      <p>{node.conditions}</p>
                    </div>
                  )}
                  {node.misconception && (
                    <div className="knowledge-note misconception">
                      <strong>易错点</strong>
                      <p>{node.misconception}</p>
                    </div>
                  )}
                  {node.example && (
                    <div className="knowledge-example">
                      <strong>联系本项目</strong>
                      <p>{node.example}</p>
                    </div>
                  )}
                  <h3>来源定位</h3>
                  <SourceLinks references={node.references} notify={notify} />
                </>
              ) : detailTab === "relations" ? (
                <>
                  {selectedEdge && (
                    <div className="edge-explanation">
                      <strong>已选关系</strong>
                      {(() => {
                        const e = graph.edges.find(
                          (x) => x.id === selectedEdge,
                        );
                        return (
                          <>
                            <p>
                              {nodesById[e.source].label}{" "}
                              <ArrowRight size={13} /> {e.label}{" "}
                              <ArrowRight size={13} />{" "}
                              {nodesById[e.target].label}
                            </p>
                            <small>{e.note || groups[e.group]}</small>
                          </>
                        );
                      })()}
                    </div>
                  )}
                  <p className="drawer-help">
                    概念关联可以跨课程单元跳转；“建议先学”为教学阅读顺序。
                  </p>
                  {["related", "prerequisite"].map((group) => (
                    <div className="relation-section" key={group}>
                      <h3>{groups[group]}</h3>
                      {relations
                        .filter((e) => e.group === group)
                        .map((e) => {
                          const other =
                            e.source === selected ? e.target : e.source;
                          return (
                            <button
                              className="knowledge-relation"
                              key={e.id}
                              onClick={() => choose(other)}
                            >
                              <div>
                                <small>
                                  {e.group === "prerequisite"
                                    ? e.source === selected
                                      ? "下一步阅读"
                                      : "建议先读"
                                    : e.source === selected
                                      ? e.label
                                      : "← " + e.label}
                                </small>
                                <strong>{nodesById[other].label}</strong>
                                <span>
                                  {
                                    graph.chapters.find(
                                      (c) => c.id === nodesById[other].chapter,
                                    )?.label
                                  }
                                </span>
                              </div>
                              <ChevronRight size={15} />
                            </button>
                          );
                        })}
                      {relations.filter((e) => e.group === group).length ===
                        0 && <p className="drawer-help">暂未整理此类关系</p>}
                    </div>
                  ))}
                </>
              ) : (
                <>
                  <p className="drawer-help">
                    示意图用于理解原理。教材页保留原始上下文，点击可放大并核对原页。
                  </p>
                  {node.images.map((im, i) => (
                    <button
                      className="knowledge-source-image"
                      key={i}
                      onClick={() => setImage(im)}
                    >
                      <img loading="lazy" src={im.url} alt={im.caption} />
                      <span>
                        {im.caption}
                        <Maximize2 size={14} />
                      </span>
                    </button>
                  ))}
                  <SourceLinks references={node.references} notify={notify} />
                </>
              )}
            </div>
            <div className="drawer-footer">
              <div>
                <button
                  className={read.includes(node.id) ? "marked" : ""}
                  onClick={() => toggleRead(node.id)}
                >
                  <Check size={15} />
                  {read.includes(node.id) ? "已标记阅读" : "标记已读"}
                </button>
                <button
                  aria-label={
                    stars.includes(node.id) ? "取消收藏" : "收藏知识点"
                  }
                  className={stars.includes(node.id) ? "starred" : ""}
                  onClick={() => toggleStar(node.id)}
                >
                  <Star
                    size={17}
                    fill={stars.includes(node.id) ? "currentColor" : "none"}
                  />
                </button>
              </div>
              <button onClick={() => onAsk(node)}>
                <MessageSquare size={15} />
                就此知识提问
              </button>
              {node.simulation && (
                <button
                  className="start-simulation"
                  onClick={() => onSimulation(node)}
                >
                  <Play size={14} />
                  配置关联仿真
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
function KnowledgeIndexStatus({ status, cards }) {
  if (!status)
    return (
      <div className="knowledge-index-status">
        <h3>
          <BookOpen size={15} />
          课程知识库
        </h3>
        <p>{cards} 张知识卡可直接浏览。全文资料检索状态由计算节点提供。</p>
      </div>
    );
  return (
    <div className="knowledge-index-status">
      <h3>
        <BookOpen size={15} />
        课程知识库与检索索引
      </h3>
      <div className="knowledge-index-counts">
        {[
          [status.cards || cards, "知识卡"],
          [status.indexed_sources || 0, "已索引来源"],
          [status.indexed_pages || 0, "资料页"],
          [status.chunks || 0, "文本片段"],
          [status.needs_ocr || 0, "待核查页"],
        ].map(([value, label]) => (
          <span key={label}>
            <strong>{value}</strong>
            {label}
          </span>
        ))}
      </div>
      <p>
        使用关键词检索（BM25）、中英术语别名与课程关系补充，回答附原页引用。无需训练大模型。
      </p>
      {!!status.source_coverage?.length && (
        <div className="source-coverage-table">
          <table>
            <thead>
              <tr>
                <th>来源</th>
                <th>资料总页</th>
                <th>已索引页</th>
                <th>片段</th>
                <th>待核查</th>
              </tr>
            </thead>
            <tbody>
              {status.source_coverage.map((row) => (
                <tr key={row.source_id}>
                  <td title={row.title}>
                    {row.source_id} · {row.title}
                  </td>
                  <td>{row.total_pages ?? "—"}</td>
                  <td>{row.indexed_pages}</td>
                  <td>{row.chunks}</td>
                  <td>{row.failed_or_needs_ocr_pages}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p>
        资料覆盖逐步扩充。空文本不一定是真正空白页；公式、图表和新提取片段仍需核查。当前没有训练模型、自动抽取物理关系或执行
        OCR。
      </p>
      <p>
        课程资料由维护者通过导入命令建立索引，扫描 PDF 需先完成 OCR。
        <a
          href="https://github.com/Weijifen666/ocean-acoustic-workbench/tree/main/docs"
          target="_blank"
          rel="noreferrer"
        >
          查看入库说明
          <ExternalLinkIcon />
        </a>
      </p>
    </div>
  );
}
function PublicOceanResources({ status }) {
  const rows = Array.isArray(status?.web_sources) ? status.web_sources : [];
  if (!rows.length) return null;
  return (
    <section className="public-ocean-resources" aria-label="公开海洋知识来源">
      <h2>公开海洋知识</h2>
      <p>
        {status.successful_web_documents || 0} 篇官方网页正文 ·{" "}
        {status.reference_guides || 0} 条项目参考导读 · {status.chunks || 0}{" "}
        个可检索片段。课程资料之外，也可直接查阅这些公开来源。
      </p>
      <details>
        <summary>查看 {rows.length} 个来源与更新时间</summary>
        <div className="public-source-table">
          <table>
            <thead>
              <tr>
                <th>资料与机构</th>
                <th>接入方式</th>
                <th>原页更新</th>
                <th>抓取日期</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((source) => (
                <tr key={source.id}>
                  <td>
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.title_zh || source.title}
                      <ArrowUpRight size={12} />
                    </a>
                    <small>{source.organization}</small>
                    <p>{source.guide_zh}</p>
                  </td>
                  <td>
                    {source.content_policy === "metadata_only"
                      ? "数据入口 · 尚未取数"
                      : source.content_policy === "original_project_summary"
                        ? "项目自写导读"
                        : source.chunks
                          ? "官方正文快照"
                          : "正文未入库"}
                    {source.stale && <small>快照待刷新</small>}
                    <small title={source.license?.note}>
                      {typeof source.license === "string"
                        ? source.license
                        : source.license?.name}
                    </small>
                  </td>
                  <td>{source.source_updated_at || "原页未提供"}</td>
                  <td>
                    {source.fetched_at
                      ? source.fetched_at.slice(0, 10)
                      : "尚未取得"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="public-source-note">
        网页快照按清单定期检查并保留来源时间；访问日期不等于观测日期。动态数据入口尚未接通实时海况，不作为当前海温或海平面数值。中文标题与导读由本项目整理。
      </p>
    </section>
  );
}
function ExternalLinkIcon() {
  return <ArrowUpRight size={12} />;
}
function SourceLinks({ references, notify }) {
  return (
    <div className="knowledge-source-links">
      {references.map((r, i) => (
        <React.Fragment key={i}>
          {r.pdf_page ? (
            <a
              href={`/api/source/${r.source_id}/page/${r.pdf_page}`}
              target="_blank"
              rel="noreferrer"
            >
              <BookOpen size={13} />
              <span>
                {r.source_id} · PDF 第 {r.pdf_page} 页<small>{r.locator}</small>
              </span>
              <ArrowUpRight size={13} />
            </a>
          ) : (
            <a href={r.code_url} target="_blank" rel="noreferrer">
              <FileText size={13} />
              <span>
                {r.locator?.startsWith("backend/") ? "本项目" : r.source_id} ·{" "}
                {r.locator}
              </span>
              <ArrowUpRight size={13} />
            </a>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
function CourseUniverse({ chapters, knowledge, read, choose }) {
  return (
    <div className="course-overview">
      <div className="overview-intro">
        <h2>课程单元</h2>
        <p>点击单元查看关系图，或直接打开知识点。无需配置大模型。</p>
      </div>
      <div className="overview-table-head">
        <span>单元与研究问题</span>
        <span>知识点</span>
        <span>阅读情况</span>
      </div>
      <div className="overview-units">
        {chapters.map((chapter) => {
          const items = knowledge.filter((node) => node.chapter === chapter.id);
          const done = items.filter((node) => read.includes(node.id)).length;
          return (
            <section className="overview-unit" key={chapter.id}>
              <button
                className="overview-unit-main"
                onClick={() => choose(chapter.id)}
              >
                <span className="overview-unit-index">
                  {String(chapter.number).padStart(2, "0")}
                </span>
                <div>
                  <h3>{chapter.label}</h3>
                  <p>{chapter.description}</p>
                </div>
                <span className="overview-count">{items.length}</span>
                <span className="overview-progress">
                  {done} / {items.length}
                  <ChevronRight size={14} />
                </span>
              </button>
              <div className="overview-knowledge-links">
                {items.map((node) => (
                  <button key={node.id} onClick={() => choose(node.id)}>
                    {read.includes(node.id) && <Check size={11} />}
                    <span>{node.label}</span>
                  </button>
                ))}
              </div>
            </section>
          );
        })}
      </div>
      <div className="overview-footer">
        <Network size={14} />
        关系图保留“父子关系”“概念关联”“建议先学”三种不同含义。
      </div>
    </div>
  );
}
function positionsFor(nodes, view, chapter, chapters, layout) {
  const positions = {},
    leaves = nodes.filter((n) => n.kind === "knowledge");
  if (view === "chapter") {
    positions[chapter] = { x: 350, y: 290 };
    leaves.forEach((n, i) => {
      const a = (i / leaves.length) * Math.PI * 2 - Math.PI / 2;
      positions[n.id] =
        layout === "tree"
          ? { x: 180 + (i % 4) * 185, y: 170 + Math.floor(i / 4) * 180 }
          : { x: 350 + Math.cos(a) * 225, y: 290 + Math.sin(a) * 215 };
    });
    if (layout === "tree") positions[chapter] = { x: 450, y: 35 };
  } else {
    positions.course = { x: 700, y: 570 };
    chapters.forEach((c, i) => {
      const angle = (i / chapters.length) * Math.PI * 2 - Math.PI / 2;
      const center = {
        x: 700 + Math.cos(angle) * 470,
        y: 570 + Math.sin(angle) * 410,
      };
      positions[c.id] = center;
      const items = leaves.filter((n) => n.chapter === c.id);
      items.forEach((n, j) => {
        const a = (j / items.length) * Math.PI * 2;
        positions[n.id] =
          layout === "tree"
            ? { x: 150 + i * 245, y: 180 + j * 100 }
            : {
                x: center.x + Math.cos(a) * 155,
                y: center.y + Math.sin(a) * 130,
              };
      });
      if (layout === "tree") positions[c.id] = { x: 150 + i * 245, y: 65 };
    });
  }
  return positions;
}
function KnowledgeCanvas({
  theme,
  graph,
  chapter,
  view,
  layout,
  selected,
  groups,
  search,
  neighborsOnly,
  read,
  connection,
  choose,
  onEdge,
  graphRef,
}) {
  const ref = useRef(null),
    cy = useRef(null),
    renderChapter = view === "chapter" ? chapter : "";
  const baseNodes = useMemo(
    () =>
      graph.nodes.filter(
        (n) => view === "all" || n.id === chapter || n.chapter === chapter,
      ),
    [graph, view, renderChapter],
  );
  const ids = new Set(baseNodes.map((n) => n.id));
  const baseEdges = graph.edges.filter(
    (e) => groups.includes(e.group) && ids.has(e.source) && ids.has(e.target),
  );
  useEffect(() => {
    const c = cytoscape({
      container: ref.current,
      elements: [
        ...baseNodes.map((n) => ({
          data: {
            id: n.id,
            label: n.label,
            color: n.color,
            size: n.kind === "course" ? 100 : n.kind === "chapter" ? 85 : 32,
            kind: n.kind,
          },
        })),
        ...baseEdges.map((e) => ({
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.label,
            group: e.group,
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            shape: "round-rectangle",
            width: 120,
            height: 40,
            "background-color": theme === "light" ? "#f8fafc" : "#253449",
            "background-opacity": 1,
            "border-width": 1,
            "border-color": "data(color)",
            "border-opacity": 0.8,
            label: "data(label)",
            "font-family": "Microsoft YaHei,Segoe UI,sans-serif",
            "font-size": 14,
            color: theme === "light" ? "#355276" : "#d8e7ff",
            "text-wrap": "wrap",
            "text-max-width": 120,
            "text-valign": "center",
            "text-margin-y": 0,
            "text-outline-color": theme === "light" ? "#eef4fb" : "#0d213e",
            "text-outline-width": 0,
          },
        },
        {
          selector: 'node[kind="chapter"]',
          style: {
            width: 120,
            height: 44,
            "background-opacity": 1,
            "border-width": 2,
            "font-size": 14,
            "font-weight": "bold",
            "text-valign": "center",
            "text-margin-y": 0,
            "text-max-width": 72,
          },
        },
        {
          selector: 'node[kind="course"]',
          style: {
            width: 125,
            height: 46,
            "background-opacity": 1,
            "font-size": 15,
            "text-valign": "center",
            "text-margin-y": 0,
            "font-weight": "bold",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "#607d9d",
            "target-arrow-color": "#7894b2",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.5,
          },
        },
        {
          selector: 'edge[group="hierarchy"]',
          style: {
            "target-arrow-shape": "none",
            "line-color": "#436288",
            opacity: 0.45,
          },
        },
        {
          selector: 'edge[group="prerequisite"]',
          style: {
            "line-style": "dashed",
            "line-color": "#b59b69",
            "target-arrow-color": "#b59b69",
          },
        },
        {
          selector: ".selected",
          style: {
            "border-width": 3,
            "border-color": theme === "light" ? "#385b88" : "#ecf4ff",
            "border-opacity": 1,
            "background-opacity": 1,
            "font-weight": "bold",
          },
        },
        { selector: ".muted", style: { opacity: 0.14 } },
        {
          selector: ".related-edge",
          style: {
            label: "data(label)",
            width: 2.3,
            "line-color": theme === "light" ? "#3b718e" : "#b0cbea",
            "target-arrow-color": theme === "light" ? "#3b718e" : "#b0cbea",
            opacity: 0.9,
            "font-size": 14,
            color: theme === "light" ? "#355276" : "#dceaff",
            "text-background-color": theme === "light" ? "#edf3fb" : "#142d4f",
            "text-background-opacity": 1,
            "text-background-padding": 3,
            "text-rotation": "autorotate",
          },
        },
        {
          selector: ".read",
          style: { "border-width": 4, "border-color": "#3b9271" },
        },
        {
          selector: ".path",
          style: {
            "border-color": "#ffe18f",
            "border-width": 5,
            "line-color": "#ffdf8b",
            "target-arrow-color": "#ffdf8b",
            opacity: 1,
          },
        },
        {
          selector: ".match",
          style: { "border-color": "#ffdc85", "border-width": 5 },
        },
      ],
      layout: {
        name: layout === "circle" ? "circle" : "preset",
        positions: positionsFor(
          baseNodes,
          view,
          chapter,
          graph.chapters,
          layout,
        ),
        padding: 48,
        fit: true,
      },
      minZoom: 0.18,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });
    cy.current = c;
    graphRef.current = c;
    c.on("tap", "node", (e) => choose(e.target.id()));
    c.on("tap", "edge", (e) => onEdge(e.target.id()));
    c.on("mouseover", "node", (e) => {
      c.container().style.cursor = "pointer";
      if (e.target.data("kind") === "knowledge")
        e.target.style("font-weight", "bold");
    });
    c.on("mouseout", "node", (e) => {
      c.container().style.cursor = "default";
      if (!e.target.hasClass("selected"))
        e.target.style("font-weight", "normal");
    });
    const observer = new ResizeObserver(() => c.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      c.destroy();
      cy.current = null;
      graphRef.current = null;
    };
  }, [graph, view, renderChapter, layout, theme, groups.join("|")]);
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.elements().removeClass("selected muted related-edge read path match");
    read.forEach((id) => c.getElementById(id).addClass("read"));
    if (selected) {
      const node = c.getElementById(selected);
      node.addClass("selected");
      node.connectedEdges().addClass("related-edge");
      if (neighborsOnly) {
        const near = node.closedNeighborhood();
        c.elements().difference(near).addClass("muted");
      }
    }
    if (search) {
      c.nodes().forEach((n) => {
        if (
          [
            n.data("label"),
            ...(graph.nodes.find((x) => x.id === n.id())?.tags || []),
            graph.nodes.find((x) => x.id === n.id())?.overview || "",
          ]
            .join(" ")
            .toLowerCase()
            .includes(search.toLowerCase())
        )
          n.addClass("match");
        else n.addClass("muted");
      });
    }
    if (connection?.nodes?.length) {
      connection.nodes.forEach((id) => c.getElementById(id).addClass("path"));
      connection.edges.forEach((id) => c.getElementById(id).addClass("path"));
    }
  }, [
    selected,
    read,
    search,
    neighborsOnly,
    connection,
    graph,
    view,
    chapter,
    layout,
    theme,
    groups.join("|"),
  ]);
  return (
    <div ref={ref} className="knowledge-canvas" aria-label="交互知识关系图" />
  );
}
