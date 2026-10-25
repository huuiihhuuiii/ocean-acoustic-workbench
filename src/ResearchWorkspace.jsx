import React, { useEffect, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  Download,
  ExternalLink,
  Loader2,
  LogIn,
  MoreHorizontal,
  Plus,
  Save,
  Users,
  X,
} from "lucide-react";
import { AnswerMarkdown } from "./RichMessage";
import { useAccount } from "./account";
import "./research-workspace.css";
async function request(path, body, method) {
  const response = await fetch("/api/workspaces" + path, {
    credentials: "same-origin",
    method: method || (body ? "POST" : "GET"),
    headers: { "Content-Type": "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(
      typeof result?.detail === "string" ? result.detail : "课题请求未完成。",
    );
    error.status = response.status;
    throw error;
  }
  return result;
}
const when = (value) =>
  value ? new Date(value).toLocaleDateString("zh-CN") : "";
const emptyNote = { title: "", body: "", source_url: "", source_note: "" };

export default function ResearchWorkspace({ notify, pendingNote, onConsumed }) {
  const account = useAccount();
  const [workspaces, setWorkspaces] = useState([]),
    [selected, setSelected] = useState(null),
    [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [create, setCreate] = useState(false),
    [title, setTitle] = useState(""),
    [description, setDescription] = useState("");
  const [editing, setEditing] = useState(false),
    [note, setNote] = useState(emptyNote),
    [join, setJoin] = useState(false),
    [joinToken, setJoinToken] = useState("");
  const [invite, setInvite] = useState(null),
    [copied, setCopied] = useState(false),
    [preview, setPreview] = useState(null);
  async function loadList(preferred) {
    const result = await request("");
    const rows = result.workspaces || [];
    setWorkspaces(rows);
    const id = preferred || selected || rows[0]?.id;
    if (id) {
      setSelected(id);
      setDetail(await request("/" + encodeURIComponent(id)));
    } else {
      setSelected(null);
      setDetail(null);
    }
  }
  useEffect(() => {
    if (!account.authenticated) return;
    setBusy(true);
    loadList()
      .catch((error) => setError(error.message))
      .finally(() => setBusy(false));
  }, [account.authenticated]);
  useEffect(() => {
    if (pendingNote && account.authenticated) {
      setNote({ ...emptyNote, ...pendingNote });
      setEditing(true);
      onConsumed?.();
    }
  }, [pendingNote, account.authenticated]);
  async function choose(id) {
    if (busy) return;
    setBusy(true);
    setError("");
    setInvite(null);
    setCopied(false);
    setPreview(null);
    try {
      const value = await request("/" + encodeURIComponent(id));
      setSelected(id);
      setDetail(value);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function createWorkspace() {
    if (!title.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const value = await request("", {
        title: title.trim(),
        description: description.trim(),
      });
      const id = value.workspace?.id;
      setCreate(false);
      setTitle("");
      setDescription("");
      await loadList(id);
      notify?.("课题已创建，可邀请同组成员。");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function joinWorkspace() {
    if (!joinToken.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const value = await request("/join", { token: joinToken.trim() });
      setJoinToken("");
      setJoin(false);
      await loadList(value.workspace?.id || value.workspace_id);
      notify?.("已加入课题。");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function generateInvite() {
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    setCopied(false);
    try {
      setInvite(
        (await request("/" + encodeURIComponent(selected) + "/invites", {}))
          .invite,
      );
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function revokeInvite() {
    if (!invite || busy) return;
    setBusy(true);
    try {
      await request(
        "/" +
          encodeURIComponent(selected) +
          "/invites/" +
          encodeURIComponent(invite.id),
        undefined,
        "DELETE",
      );
      setInvite(null);
      notify?.("该邀请已撤销。");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function saveNote() {
    if (
      !selected ||
      !note.title.trim() ||
      !note.body.trim() ||
      note.body.length > 20000 ||
      busy
    )
      return;
    setBusy(true);
    setError("");
    try {
      await request("/" + encodeURIComponent(selected) + "/artifacts", {
        ...note,
        title: note.title.trim(),
        body: note.body.trim(),
      });
      setNote(emptyNote);
      setEditing(false);
      setDetail(await request("/" + encodeURIComponent(selected)));
      await loadList(selected);
      notify?.("研究笔记已保存到这个课题。");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  function exportNotes() {
    if (!detail) return;
    const body =
      `# ${detail.workspace.title}\n\n${detail.workspace.description || ""}\n\n` +
      (detail.artifacts || [])
        .map(
          (item) =>
            `## ${item.title}\n\n${item.body}\n\n${item.source_url ? "来源：" + item.source_url + "\n\n" : ""}${item.source_note || ""}\n\n作者：${item.author_name || "成员"} · ${item.created_at || ""}\n\n---`,
        )
        .join("\n\n");
    const url = URL.createObjectURL(
      new Blob([body], { type: "text/markdown;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "课题研究笔记.md";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }
  if (account.loading)
    return (
      <div className="empty panel">
        <Loader2 className="spin" size={22} />
        <p>正在读取个人空间…</p>
      </div>
    );
  if (!account.available)
    return (
      <div className="workspace-login card-base">
        <Users size={28} />
        <h1>共享课题</h1>
        <p>此部署暂时无法读取平台账户，请稍后重试。</p>
      </div>
    );
  if (!account.authenticated)
    return (
      <div className="workspace-login card-base">
        <div className="workspace-login-icon">
          <Users size={30} />
        </div>
        <span className="section-kicker">四人小组 · 同一份研究</span>
        <h1>把发现，积累成共同的成果。</h1>
        <p>
          登录后创建课题、邀请组员，保存带出处的研究笔记。
          <br />
          聊天与模型密钥保留在个人空间。
        </p>
        <a
          className="btn-regular"
          href={account.sign_in_url || "/signin-with-chatgpt?return_to=%2F"}
          target="_top"
        >
          <LogIn size={16} />
          登录并进入课题
        </a>
        <small>访客数据不会自动合并到登录账户。</small>
      </div>
    );
  const owner = detail?.workspace?.role === "owner";
  const artifacts = detail?.artifacts || [];
  return (
    <section className="research-workspace">
      <header className="research-heading">
        <div>
          <span className="section-kicker">课题空间</span>
          <h1>一起研究，留下依据。</h1>
          <p>{account.display_name} 的课程课题 · 笔记、出处与小组协作</p>
        </div>
        <details className="research-more">
          <summary aria-label="课题更多操作">
            <MoreHorizontal size={19} />
          </summary>
          <div className="float-panel">
            {owner && (
              <button onClick={generateInvite} disabled={busy}>
                <Users size={14} />
                生成组员邀请
              </button>
            )}
            <button onClick={() => setJoin(true)}>
              <Plus size={14} />
              接受邀请
            </button>
            <button disabled={!artifacts.length} onClick={exportNotes}>
              <Download size={14} />
              导出课题笔记
            </button>
            <a
              href={
                account.sign_out_url || "/signout-with-chatgpt?return_to=%2F"
              }
              target="_top"
            >
              退出登录
            </a>
          </div>
        </details>
      </header>
      {error && (
        <p className="research-error" role="status">
          {error}
        </p>
      )}
      {join && (
        <div className="research-inline card-base">
          <div>
            <h2>加入同组课题</h2>
            <button
              onClick={() => {
                setJoin(false);
                setJoinToken("");
              }}
              aria-label="关闭加入课题"
            >
              <X size={16} />
            </button>
          </div>
          <label>
            粘贴组员发给你的邀请
            <input
              aria-label="课题邀请口令"
              type="password"
              autoComplete="off"
              value={joinToken}
              onChange={(event) => setJoinToken(event.target.value)}
              placeholder="一次性邀请口令"
            />
          </label>
          <button
            className="btn-regular"
            disabled={busy || !joinToken.trim()}
            onClick={joinWorkspace}
          >
            接受邀请
          </button>
        </div>
      )}
      {invite && (
        <div className="research-inline invite-card card-base">
          <div>
            <h2>将邀请交给同组成员</h2>
            <button
              onClick={() => {
                setInvite(null);
                setCopied(false);
              }}
              aria-label="关闭邀请口令"
            >
              <X size={16} />
            </button>
          </div>
          <p>
            一次性邀请，有效至{" "}
            {invite.expires_at
              ? new Date(invite.expires_at).toLocaleString("zh-CN")
              : "服务端指定时间"}
            。请复制后手动发给一位组员。
          </p>
          <div className="invite-token">
            <code>{invite.token}</code>
            <button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(invite.token);
                  setCopied(true);
                } catch {
                  setError("复制未完成，可手动选中口令。");
                }
              }}
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}{" "}
              {copied ? "已复制" : "复制邀请"}
            </button>
          </div>
          <button
            className="revoke-invite"
            disabled={busy}
            onClick={revokeInvite}
          >
            撤销这份邀请
          </button>
        </div>
      )}
      <div className="research-layout">
        <aside className="research-list card-base">
          <header>
            <span>我的课题</span>
            <button
              onClick={() => setCreate((value) => !value)}
              aria-label="新建课题"
              title="新建课题"
            >
              <Plus size={16} />
            </button>
          </header>
          {create && (
            <form
              className="workspace-create"
              onSubmit={(event) => {
                event.preventDefault();
                void createWorkspace();
              }}
            >
              <input
                aria-label="课题名称"
                maxLength={100}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="课题名称"
                required
              />
              <textarea
                aria-label="课题说明"
                maxLength={500}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="研究目标（可选）"
              />
              <button className="btn-regular" disabled={busy || !title.trim()}>
                创建课题
              </button>
            </form>
          )}
          {workspaces.map((item) => (
            <button
              className={`workspace-item${selected === item.id ? " selected" : ""}`}
              key={item.id}
              disabled={busy}
              onClick={() => void choose(item.id)}
            >
              <BookOpen size={17} />
              <span>
                <strong>{item.title}</strong>
                <small>
                  {item.member_count} 位成员 · {item.artifact_count} 份笔记
                </small>
              </span>
            </button>
          ))}
          {!workspaces.length && !busy && (
            <p className="workspace-empty-list">
              从一个课题开始，或在右上角接受组员邀请。
            </p>
          )}
          {busy && !detail && (
            <Loader2 className="spin workspace-list-loading" size={18} />
          )}
        </aside>
        <section className="research-content card-base">
          {detail ? (
            <>
              <div className="research-project-title">
                <div>
                  <h2>{detail.workspace.title}</h2>
                  <p>
                    {detail.workspace.description ||
                      "记录问题、证据、实验与结论。"}
                  </p>
                </div>
                <button
                  className="btn-regular"
                  onClick={() => {
                    setEditing(true);
                    setPreview(null);
                  }}
                >
                  <Plus size={14} />
                  研究笔记
                </button>
              </div>
              <div className="research-members">
                {(detail.members || []).map((member) => (
                  <span key={member.account_id}>
                    <i>{(member.display_name || "组员").slice(0, 1)}</i>
                    {member.display_name || "组员"}
                    <small>{member.role === "owner" ? "负责人" : "组员"}</small>
                  </span>
                ))}
              </div>
              {editing && (
                <form
                  className="research-note-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void saveNote();
                  }}
                >
                  <label>
                    笔记标题
                    <input
                      maxLength={120}
                      value={note.title}
                      onChange={(event) =>
                        setNote({ ...note, title: event.target.value })
                      }
                      placeholder="例如：100Hz 与 50Hz 的传播损失对照"
                      required
                    />
                  </label>
                  <label>
                    研究内容
                    <textarea
                      className="research-body-input"
                      value={note.body}
                      onChange={(event) =>
                        setNote({ ...note, body: event.target.value })
                      }
                      placeholder="写下问题、参数、观察和结论，支持 Markdown 与公式。"
                      required
                    />
                  </label>
                  <div className="research-source-fields">
                    <label>
                      来源链接（可选）
                      <input
                        type="url"
                        value={note.source_url}
                        onChange={(event) =>
                          setNote({ ...note, source_url: event.target.value })
                        }
                        placeholder="https://..."
                      />
                    </label>
                    <label>
                      出处与页码（可选）
                      <textarea
                        value={note.source_note}
                        onChange={(event) =>
                          setNote({ ...note, source_note: event.target.value })
                        }
                        placeholder="原文页码、计算任务编号或参考说明"
                      />
                    </label>
                  </div>
                  <footer>
                    <small>
                      {note.body.length.toLocaleString()} / 20,000 字符 ·
                      仅分享这份笔记正文与出处
                    </small>
                    <div>
                      <button type="button" onClick={() => setEditing(false)}>
                        收起
                      </button>
                      <button
                        className="btn-regular"
                        disabled={
                          busy ||
                          !note.title.trim() ||
                          !note.body.trim() ||
                          note.body.length > 20000
                        }
                      >
                        <Save size={14} />
                        {busy ? "正在保存" : "保存到课题"}
                      </button>
                    </div>
                  </footer>
                </form>
              )}
              {!artifacts.length && !editing && (
                <div className="research-empty">
                  <BookOpen size={33} />
                  <h3>第一份发现，值得留下。</h3>
                  <p>整理一条回答、一次实验或一段原文，补上来源后收录。</p>
                </div>
              )}
              <div className="research-artifacts">
                {artifacts.map((item) => (
                  <article className="research-artifact" key={item.id}>
                    <button
                      className="research-artifact-heading"
                      onClick={() =>
                        setPreview(preview === item.id ? null : item.id)
                      }
                      aria-expanded={preview === item.id}
                    >
                      <span>
                        <strong>{item.title}</strong>
                        <small>
                          {item.author_name || "组员"} · {when(item.created_at)}
                        </small>
                      </span>
                      <BookOpen size={15} />
                    </button>
                    {preview === item.id && (
                      <div className="research-artifact-body">
                        <AnswerMarkdown text={item.body} />
                        {item.source_note && (
                          <p className="research-source-note">
                            出处：{item.source_note}
                          </p>
                        )}
                        {/^https:\/\//i.test(item.source_url || "") && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            核对原始来源
                            <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="research-empty">
              <Users size={36} />
              <h2>选择或创建一个课题</h2>
              <p>共享笔记与出处；模型密钥和私人会话按账户独立保存。</p>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
