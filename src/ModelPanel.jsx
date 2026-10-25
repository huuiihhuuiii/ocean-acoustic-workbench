import React, { useEffect, useState } from "react";
import {
  Cpu,
  ExternalLink,
  Check,
  ShieldCheck,
  Radio,
  RefreshCw,
  Save,
  Loader2,
  AlertCircle,
} from "lucide-react";
import "./models.css";
import { useAccount } from "./account";
const request = async (path, body) => {
  const r = await fetch("/api" + path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
};
export default function ModelPanel({ cfg, setCfg, onSave, busy, notify }) {
  const personalAccount = useAccount();
  const [catalog, setCatalog] = useState(null),
    [profiles, setProfiles] = useState({}),
    [action, setAction] = useState(""),
    [result, setResult] = useState(null),
    [account, setAccount] = useState(null),
    [custom, setCustom] = useState(false);
  useEffect(() => {
    request("/models/catalog")
      .then(setCatalog)
      .catch((e) => notify(e.message));
    request("/models/profiles")
      .then(setProfiles)
      .catch((e) => notify(e.message));
  }, [cfg.api_key_set]);
  useEffect(() => {
    setResult(null);
    setAccount(null);
  }, [cfg.provider, cfg.model, cfg.base_url, cfg.api_key]);
  if (!catalog)
    return (
      <section className="panel model-panel">正在载入供应商模型目录…</section>
    );
  const provider =
      catalog.providers.find((p) => p.id === cfg.provider) ||
      catalog.providers[0],
    rows = catalog.models.filter((m) => m.provider === provider.id),
    chosen = rows.find((m) => m.id === cfg.model);
  function switchProvider(p) {
    const saved = profiles[p.id],
      fallback = catalog.models.find((m) => m.provider === p.id);
    setCfg((c) => ({
      ...c,
      provider: p.id,
      base_url: saved?.base_url || p.base_url,
      model: saved?.model || fallback.id,
      api_key: "",
      api_key_set: !!saved?.api_key_set,
    }));
    setCustom(false);
  }
  async function run(type) {
    setAction(type);
    setResult(null);
    try {
      const data = await request("/models/" + type, {
        provider: cfg.provider,
        base_url: cfg.base_url,
        model: cfg.model,
        api_key: cfg.api_key || "",
      });
      if (type === "list") setAccount(data);
      else setResult({ ok: true, ...data });
    } catch (e) {
      setResult({ ok: false, note: e.message });
    } finally {
      setAction("");
    }
  }
  async function clearKeys() {
    setAction("clear");
    setResult(null);
    try {
      const data = await request("/session/clear-keys", {});
      setCfg((current) => ({
        ...current,
        ...data,
        api_key: "",
        api_key_set: false,
      }));
      setProfiles({});
      setAccount(null);
      notify(
        cfg.public_mode
          ? "你的全部模型密钥已从云端删除。"
          : "本机模型密钥已清除。",
      );
      window.dispatchEvent(new CustomEvent("ocean-model-config-changed"));
    } catch (error) {
      notify(error.message);
    } finally {
      setAction("");
    }
  }
  return (
    <section className="panel model-panel">
      <div className="model-panel-heading">
        <div>
          <h2>
            <Cpu size={20} />
            供应商与模型连接
          </h2>
          <p>
            {cfg.public_mode
              ? personalAccount.loading
                ? "模型连接在当前个人空间加密保存。"
                : personalAccount.authenticated
                  ? "模型连接在你的登录账户中加密保存，可跨设备使用；课题成员不会获得你的模型密钥。"
                  : "模型连接在当前访客空间加密保存。换浏览器或清除 Cookie 会建立新空间；登录账户可跨设备同步，访客密钥不会自动合并。"
              : "选择具体供应商与模型，密钥保存在本机私有目录，按供应商分别管理，不随源码同步。"}
          </p>
        </div>
        <span className="catalog-stamp">
          <ShieldCheck size={14} />
          官方文档核对 {catalog.verified_date}
        </span>
      </div>
      <div className="provider-tabs">
        {catalog.providers.map((p) => (
          <button
            key={p.id}
            className={cfg.provider === p.id ? "active" : ""}
            onClick={() => switchProvider(p)}
          >
            <span className={"provider-symbol " + p.id}>
              {p.id === "DeepSeek"
                ? "D"
                : p.id === "Qwen"
                  ? "Q"
                  : p.id === "Kimi"
                    ? "K"
                    : "G"}
            </span>
            <span>
              <strong>{p.name}</strong>
              <small>
                {catalog.models.filter((m) => m.provider === p.id).length}{" "}
                项模型预设
              </small>
            </span>
            {cfg.provider === p.id && <Check size={15} />}
          </button>
        ))}
      </div>
      <div className="model-config-columns">
        <div className="model-catalog">
          <div className="model-section-title">
            <strong>模型目录</strong>
            <a href={provider.documentation} target="_blank" rel="noreferrer">
              供应商文档
              <ExternalLink size={12} />
            </a>
          </div>
          <p className="provider-note">{provider.note}</p>
          <div className="model-card-list">
            {rows.map((m) => (
              <button
                key={m.key}
                className={
                  "model-choice " + (cfg.model === m.id ? "selected" : "")
                }
                onClick={() => {
                  setCfg((c) => ({ ...c, model: m.id }));
                  setCustom(false);
                }}
              >
                <div>
                  <span className="model-radio">
                    {cfg.model === m.id && <i />}
                  </span>
                  <strong>{m.name}</strong>
                </div>
                <code>{m.id}</code>
                <p>{m.description}</p>
                <div className="model-meta">
                  <span>开发方 {m.developer}</span>
                  <span>{m.kind}</span>
                </div>
              </button>
            ))}
          </div>
          <button
            className="custom-model-toggle"
            onClick={() => setCustom((x) => !x)}
          >
            填写账户中的其他模型标识
          </button>
          {custom && (
            <label className="model-field">
              API 模型标识
              <input
                value={cfg.model}
                onChange={(e) =>
                  setCfg((c) => ({ ...c, model: e.target.value }))
                }
                placeholder="以供应商控制台或 /models 返回为准"
              />
            </label>
          )}
        </div>
        <div className="model-connection">
          <div className="model-section-title">
            <strong>当前连接</strong>
            <span
              className={"connection-badge " + (cfg.api_key_set ? "saved" : "")}
            >
              {cfg.api_key_set ? "已保存该供应商密钥" : "尚未保存密钥"}
            </span>
          </div>
          <div className="selected-model">
            <small>{provider.name}</small>
            <h3>{chosen?.name || cfg.model}</h3>
            <code>{cfg.model}</code>
            <span>开发方：{chosen?.developer || "以官方说明为准"}</span>
            <a
              href={chosen?.documentation || provider.documentation}
              target="_blank"
              rel="noreferrer"
            >
              查看该模型说明
              <ExternalLink size={12} />
            </a>
          </div>
          <label className="model-field">
            API 接口地址
            <input
              value={cfg.base_url}
              onChange={(e) =>
                setCfg((c) => ({ ...c, base_url: e.target.value }))
              }
            />
            <small>
              {provider.id === "Qwen"
                ? "百炼可填北京业务空间专属地址，Key 地域须匹配。"
                : "使用当前供应商的标准模型 API 地址。"}
            </small>
          </label>
          <label className="model-field">
            API Key
            <input
              type="password"
              autoComplete="new-password"
              value={cfg.api_key || ""}
              onChange={(e) =>
                setCfg((c) => ({ ...c, api_key: e.target.value }))
              }
              placeholder={
                cfg.api_key_set
                  ? "已保存；留空保持该供应商密钥"
                  : "输入当前供应商的 API Key"
              }
            />
            <small>前端不会读取已保存的完整密钥。</small>
          </label>
          <div className="model-test-actions">
            <button disabled={!!action} onClick={() => run("list")}>
              {action === "list" ? (
                <Loader2 size={14} className="spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              查询账户模型
            </button>
            <button disabled={!!action} onClick={() => run("test")}>
              {action === "test" ? (
                <Loader2 size={14} className="spin" />
              ) : (
                <Radio size={14} />
              )}
              测试当前模型
            </button>
          </div>
          <p className="model-test-hint">
            测试会发起一次短模型调用，可能消耗少量
            Token。未测试时不标记为已可用。
          </p>
          {result && (
            <div
              className={
                "model-test-result " + (result.ok ? "success" : "error")
              }
            >
              <strong>{result.ok ? "当前模型调用通过" : "连接尚未通过"}</strong>
              <p>{result.note}</p>
              {result.ok && (
                <small>
                  请求 {result.requested_model}
                  <br />
                  返回 {result.response_model}
                  {result.reply && (
                    <>
                      <br />
                      响应：{result.reply}
                    </>
                  )}
                </small>
              )}
            </div>
          )}
          {account && (
            <div className="account-models">
              <strong>接口返回 {account.ids.length} 个模型</strong>
              <small>
                {account.selected_listed
                  ? "包含当前选择；仍需实际调用验证"
                  : "未列出当前选择，请核对账户权限"}
              </small>
              <div>
                {account.ids.map((id) => (
                  <button
                    key={id}
                    onClick={() => {
                      setCfg((c) => ({ ...c, model: id }));
                      setCustom(!rows.some((m) => m.id === id));
                    }}
                  >
                    {id}
                  </button>
                ))}
              </div>
            </div>
          )}
          <button
            className="apply-model"
            disabled={busy || !!action}
            onClick={onSave}
          >
            <Save size={15} />
            {busy ? "正在保存…" : "保存并应用配置"}
          </button>
          <button
            className="clear-model-keys"
            disabled={!!action || busy}
            onClick={clearKeys}
          >
            {action === "clear" ? "正在清除…" : "清除我的全部模型密钥"}
          </button>
          <div className="model-scope-note">
            <AlertCircle size={13} />
            <span>
              官方文档中的模型预设不代表账户权限已开通。知识图谱和共享模板仿真可独立使用；自动修改代码仍待接入。
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
