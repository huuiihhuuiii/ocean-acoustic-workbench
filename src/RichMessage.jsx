import React, {
  Children,
  isValidElement,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import hljs from "highlight.js/lib/core";
import matlab from "highlight.js/lib/languages/matlab";
import python from "highlight.js/lib/languages/python";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import bash from "highlight.js/lib/languages/bash";
import {
  Check,
  Copy,
  ExternalLink,
  FileText,
  Network,
  RotateCcw,
  X,
} from "lucide-react";
import { SimulationDraftCard } from "./SimulationAssist";
import { useAccount } from "./account";
import "./vendor/katex-modern.css";
import "highlight.js/styles/github.css";
import "./rich-message.css";

for (const [name, definition] of Object.entries({
  matlab,
  python,
  javascript,
  json,
  bash,
}))
  hljs.registerLanguage(name, definition);

export function evidenceRows(message = {}) {
  const evidence = Array.isArray(message.evidence) ? message.evidence : [];
  const citations = message.citations?.length ? message.citations : evidence;
  return citations.map((citation, index) => {
    const id = citation.evidence_id || citation.id || citation.citation_id;
    const chunk =
      evidence.find((item) => id && [item.id, item.evidence_id].includes(id)) ||
      citation;
    return {
      ...chunk,
      ...citation,
      text:
        chunk.text || chunk.excerpt || chunk.snippet || citation.locator || "",
      index: index + 1,
      aliases: [id, citation.citation_id, chunk.id, String(index + 1)]
        .filter(Boolean)
        .map(String),
      label:
        citation.label ||
        chunk.label ||
        citation.source_id ||
        `来源 ${index + 1}`,
    };
  });
}

// Turn only identifiers backed by this response's evidence into clickable citations.
function remarkEvidence({ rows }) {
  const aliases = new Map();
  rows.forEach((row) =>
    row.aliases.forEach((alias) => aliases.set(alias, row.index)),
  );
  return (tree) => {
    const walk = (node) => {
      if (
        !node.children ||
        ["link", "code", "inlineCode", "math", "inlineMath"].includes(node.type)
      )
        return;
      node.children = node.children.flatMap((child) => {
        if (child.type !== "text") {
          walk(child);
          return [child];
        }
        const pattern = /\[([A-Za-z0-9_:./@-]+)\]|【([A-Za-z0-9_:./@-]+)】/g;
        const result = [];
        let cursor = 0;
        let match;
        while ((match = pattern.exec(child.value))) {
          const index = aliases.get(match[1] || match[2]);
          if (!index) continue;
          if (match.index > cursor)
            result.push({
              type: "text",
              value: child.value.slice(cursor, match.index),
            });
          result.push({
            type: "link",
            url: `#ocean-evidence-${index}`,
            children: [{ type: "text", value: String(index) }],
          });
          cursor = pattern.lastIndex;
        }
        if (!result.length) return [child];
        if (cursor < child.value.length)
          result.push({ type: "text", value: child.value.slice(cursor) });
        return result;
      });
    };
    walk(tree);
  };
}

function normalizeMath(text) {
  return text
    .split(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g)
    .map((part) =>
      part.startsWith("`") || part.startsWith("~~~")
        ? part
        : part
            .replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => `\n$$\n${math}\n$$\n`)
            .replace(/\\\(([\s\S]*?)\\\)/g, (_, math) => `$${math}$`),
    )
    .join("");
}

function CodeBlock({ children }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const child = Children.toArray(children).find(isValidElement);
  const raw = String(child?.props.children || "").replace(/\n$/, "");
  const language =
    /language-([^ ]+)/.exec(child?.props.className || "")?.[1] || "text";
  const selected =
    { js: "javascript", py: "python", shell: "bash", m: "matlab" }[language] ||
    language;
  const rendered = useMemo(
    () =>
      hljs.getLanguage(selected)
        ? hljs.highlight(raw, { language: selected, ignoreIllegals: true })
            .value
        : null,
    [raw, selected],
  );
  return (
    <div className="answer-code">
      <div className="answer-code-bar">
        <span>{language === "text" ? "代码" : language}</span>
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(raw);
              setCopied(true);
              setCopyError(false);
              clearTimeout(timer.current);
              timer.current = setTimeout(() => setCopied(false), 1800);
            } catch {
              setCopyError(true);
            }
          }}
          aria-label="复制代码"
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}{" "}
          {copied ? "已复制" : copyError ? "复制未完成" : "复制"}
        </button>
      </div>
      <pre>
        <code
          className={`hljs language-${language}`}
          {...(rendered !== null
            ? { dangerouslySetInnerHTML: { __html: rendered } }
            : { children: raw })}
        />
      </pre>
    </div>
  );
}

export function AnswerMarkdown({
  text = "",
  rows = [],
  onEvidence,
  compact = false,
}) {
  const plugins = useMemo(
    () => [remarkGfm, remarkMath, [remarkEvidence, { rows }]],
    [rows],
  );
  return (
    <div className={`answer-markdown${compact ? " compact" : ""}`}>
      <ReactMarkdown
        remarkPlugins={plugins}
        rehypePlugins={[
          [rehypeKatex, { strict: false, throwOnError: false, trust: false }],
        ]}
        urlTransform={(url) =>
          url.startsWith("#ocean-evidence-") ? url : defaultUrlTransform(url)
        }
        components={{
          pre: CodeBlock,
          table: ({ children }) => (
            <div className="answer-table">
              <table>{children}</table>
            </div>
          ),
          a: ({ href, children }) =>
            href?.startsWith("#ocean-evidence-") ? (
              <button
                type="button"
                className="inline-evidence"
                aria-label={`查看来源 ${String(children)}`}
                onClick={() =>
                  onEvidence?.(
                    Number(href.slice("#ocean-evidence-".length)) - 1,
                  )
                }
              >
                {children}
              </button>
            ) : (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
          img: ({ alt }) => (
            <span className="answer-image-reference">
              [图片：{alt || "请核对来源"}]
            </span>
          ),
        }}
      >
        {normalizeMath(text)}
      </ReactMarkdown>
    </div>
  );
}

function sourceUrl(row) {
  const value =
    row.url ||
    row.source_url ||
    (row.source_id && row.pdf_page
      ? `/api/source/${encodeURIComponent(row.source_id)}/page/${row.pdf_page}`
      : null);
  return typeof value === "string" &&
    (/^https:\/\//i.test(value) || value.startsWith("/api/"))
    ? value
    : null;
}

export function EvidenceDrawer({ rows, initial = 0, onClose, onKnowledge }) {
  const [selected, setSelected] = useState(initial);
  const close = useRef(null);
  const prior = useRef(document.activeElement);
  const row = rows[selected] || rows[0];
  useEffect(() => {
    close.current?.focus({ preventScroll: true });
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      prior.current?.focus?.({ preventScroll: true });
    };
  }, []);
  if (!row) return null;
  const url = sourceUrl(row);
  const kind = ["reviewed_course_card", "knowledge_card"].includes(
    row.evidence_type,
  )
    ? "课程知识卡"
    : row.evidence_type === "public_web" || row.fetched_at
      ? "公开资料快照"
      : "检索原文片段";
  return createPortal(
    <div className="evidence-backdrop" onClick={onClose}>
      <section
        className="evidence-drawer card-base"
        role="dialog"
        aria-modal="true"
        aria-label="回答证据"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.stopPropagation();
            onClose();
          }
          if (event.key === "Tab") {
            const items = [
              ...event.currentTarget.querySelectorAll("button, a[href]"),
            ].filter((item) => !item.disabled);
            const first = items[0],
              last = items.at(-1);
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <header>
          <div>
            <span className="section-kicker">核对出处</span>
            <h2>这条回答的依据</h2>
          </div>
          <button ref={close} onClick={onClose} aria-label="关闭证据抽屉">
            <X size={20} />
          </button>
        </header>
        <nav aria-label="选择引用">
          {rows.map((item, index) => (
            <button
              key={index}
              onClick={() => setSelected(index)}
              aria-current={selected === index ? "true" : undefined}
            >
              {item.index}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="evidence-body">
          <span className="evidence-kind">{kind}</span>
          <h3>{row.label}</h3>
          <div className="evidence-location">
            {row.organization || row.source_id}
            {row.pdf_page ? ` · PDF 第 ${row.pdf_page} 页` : ""}
            {row.locator ? ` · ${row.locator}` : ""}
          </div>
          <blockquote>
            {row.text || "此来源未提供可展示的片段，请核对原始出处。"}
          </blockquote>
          {row.formula && <AnswerMarkdown text={`$$${row.formula}$$`} />}{" "}
          {row.conditions && (
            <p className="evidence-condition">适用条件：{row.conditions}</p>
          )}
          {row.fetched_at && (
            <p className="evidence-condition">
              采集时间：{row.fetched_at}；采集时间不等于观测时间。
            </p>
          )}
          <p className="evidence-disclosure">
            这是本次返回的检索证据，仍需结合原文核对适用条件。
          </p>
          <div className="evidence-links">
            {url && (
              <a href={url} target="_blank" rel="noreferrer">
                <ExternalLink size={15} />
                查看原始出处
              </a>
            )}
            {row.node_id && onKnowledge && (
              <button
                onClick={() => {
                  onClose();
                  onKnowledge(row.node_id);
                }}
              >
                <Network size={15} />
                打开知识点
              </button>
            )}
          </div>
        </div>
      </section>
    </div>,
    document.body,
  );
}

export default function RichMessage({
  message,
  compact = false,
  onKnowledge,
  onSimulation,
  onRetry,
  onSettings,
}) {
  const account = useAccount();
  const rows = useMemo(
    () => evidenceRows(message),
    [message.evidence, message.citations],
  );
  const [opened, setOpened] = useState(null);
  const used = message.model_used === true;
  const stopped = message.status === "stopped";
  const pending = ["pending", "streaming"].includes(message.status);
  return (
    <div
      className={`rich-message${message.request_failed ? " has-error" : ""}`}
    >
      <AnswerMarkdown
        text={message.text}
        rows={rows}
        onEvidence={setOpened}
        compact={compact}
      />
      {message.status === "streaming" && message.text && (
        <span className="stream-caret" aria-label="正在生成" />
      )}
      {message.completion_notice && (
        <p className="answer-completion-notice" role="status">
          {message.completion_notice}
        </p>
      )}
      {stopped && (
        <p className="answer-stopped">已停止 · 已保留收到的部分回答</p>
      )}
      {message.request_failed && (
        <div className="answer-recovery">
          {onRetry && message.retry_text && (
            <button onClick={() => onRetry(message)}>
              <RotateCcw size={13} />
              重试这次请求
            </button>
          )}
          {onSettings &&
            /401|AUTH|KEY|模型|密钥/i.test(
              `${message.error_code} ${message.error}`,
            ) && <button onClick={onSettings}>检查模型连接</button>}
        </div>
      )}
      {!!rows.length && (
        <div className="answer-evidence-chips" aria-label="回答来源">
          {rows.slice(0, compact ? 2 : 3).map((row, index) => (
            <button
              key={index}
              onClick={() => setOpened(index)}
              title={row.label}
            >
              <span>{row.index}</span>
              {row.label}
            </button>
          ))}
          {rows.length > (compact ? 2 : 3) && (
            <button onClick={() => setOpened(0)}>
              +{rows.length - (compact ? 2 : 3)} 条
            </button>
          )}
        </div>
      )}
      {!pending && !message.request_failed && (
        <details className="answer-identity">
          <summary>
            {stopped
              ? "本次请求记录"
              : used
                ? message.response_model || "模型返回记录"
                : message.model_used === false
                  ? "资料检索 · 未调用模型"
                  : "调用记录未提供"}
          </summary>
          <dl>
            <div>
              <dt>供应商</dt>
              <dd>{message.model_provider || "未提供"}</dd>
            </div>
            <div>
              <dt>请求入口</dt>
              <dd>{message.requested_model || "未提供"}</dd>
            </div>
            <div>
              <dt>返回标识</dt>
              <dd>{message.response_model || "未提供"}</dd>
            </div>
            <div>
              <dt>回答范围</dt>
              <dd>
                {message.knowledge_scope === "general"
                  ? "资料 + 模型知识"
                  : message.knowledge_scope === "course"
                    ? "仅依据资料"
                    : "未提供"}
              </dd>
            </div>
          </dl>
          {message.coverage_notice && <p>{message.coverage_notice}</p>}
          {account.authenticated && (
            <button
              type="button"
              className="answer-save-note"
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("ocean-save-research-note", {
                    detail: {
                      title:
                        message.text
                          .replace(/[#*`]/g, "")
                          .split("\n")
                          .find(Boolean)
                          ?.slice(0, 100) || "研究笔记",
                      body: message.text,
                      source_url: rows.find((row) =>
                        /^https:\/\//i.test(sourceUrl(row) || ""),
                      )
                        ? sourceUrl(
                            rows.find((row) =>
                              /^https:\/\//i.test(sourceUrl(row) || ""),
                            ),
                          )
                        : "",
                      source_note: rows
                        .map(
                          (row) =>
                            `${row.index}. ${row.label}${row.pdf_page ? " · PDF 第 " + row.pdf_page + " 页" : ""}${sourceUrl(row) ? " · " + sourceUrl(row) : ""}`,
                        )
                        .join("\n"),
                    },
                  }),
                )
              }
            >
              <FileText size={12} />
              整理为课题笔记
            </button>
          )}
        </details>
      )}
      {message.simulation_draft && (
        <SimulationDraftCard
          draft={message.simulation_draft}
          onApply={onSimulation}
          compact={compact}
        />
      )}
      {opened !== null && (
        <EvidenceDrawer
          rows={rows}
          initial={opened}
          onClose={() => setOpened(null)}
          onKnowledge={onKnowledge}
        />
      )}
    </div>
  );
}
