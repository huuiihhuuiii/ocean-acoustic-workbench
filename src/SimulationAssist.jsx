import React, { useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  FlaskConical,
  Loader2,
  MessageSquare,
  X,
} from "lucide-react";
import "./simulation-assist.css";

const fieldNames = {
  template: "环境模板",
  frequencies_hz: "频率 / Hz",
  source_depths_m: "声源深度 / m",
  receiver_depth_m: "接收深度 / m",
  range_min_km: "起始距离 / km",
  range_max_km: "终止距离 / km",
  range_points: "距离采样点",
  depth_points: "深度采样点",
};
const planValue = (value) =>
  Array.isArray(value) ? value.join("、") : String(value);
export function SimulationDraftCard({ draft, onApply, compact = false }) {
  if (!draft) return null;
  const plan = draft.draft_plan || {};
  const missing = draft.missing_fields || [];
  const errors = draft.validation_errors || [];
  const unsupported = draft.unsupported_requests || [];
  const ready =
    draft.ready_for_preview === true &&
    !missing.length &&
    !errors.length &&
    !unsupported.length;
  return (
    <section
      className={`simulation-draft${compact ? " compact" : ""}`}
      aria-label="仿真参数草案"
    >
      <div className="draft-heading">
        <span>
          <FlaskConical size={16} />
          仿真参数草案
        </span>
        <small>{ready ? "待你确认" : "还需补充条件"}</small>
      </div>
      <dl>
        {Object.entries(plan).map(([key, value]) => (
          <div key={key}>
            <dt>{fieldNames[key] || key}</dt>
            <dd>{planValue(value)}</dd>
          </div>
        ))}
      </dl>
      {!!missing.length && (
        <div className="draft-missing">
          <strong>请补充</strong>
          {missing.map((item, index) => (
            <p key={item.field || index}>
              {item.question || item.label || String(item)}
            </p>
          ))}
        </div>
      )}
      {!!errors.length && (
        <div className="draft-missing">
          {errors.map((item, index) => (
            <p key={index}>{item.message || String(item)}</p>
          ))}
        </div>
      )}
      {!!unsupported.length && (
        <div className="draft-missing">
          {unsupported.map((item, index) => (
            <p key={index}>
              {typeof item === "string" ? item : item.message || item.label}
            </p>
          ))}
        </div>
      )}
      {!!(draft.assumptions?.length || draft.warnings?.length) && (
        <details>
          <summary>默认采样与注意事项</summary>
          <ul>
            {[...(draft.assumptions || []), ...(draft.warnings || [])].map(
              (item, index) => (
                <li key={index}>
                  {typeof item === "string"
                    ? item
                    : item.reason
                      ? `${fieldNames[item.field] || item.field}：${item.value}（${item.reason}）`
                      : item.message || JSON.stringify(item)}
                </li>
              ),
            )}
          </ul>
        </details>
      )}
      <footer>
        <small>
          参数解析草案 ·{" "}
          {draft.model_used === false ? "未调用模型" : draft.parser || "待核查"}
          <br />
          确认计划后才提交 MATLAB；不会自动运行。
        </small>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(draft)}
            disabled={!ready}
          >
            {compact ? "检查计划" : "填入参数并检查"}
            <ArrowRight size={14} />
          </button>
        )}
      </footer>
    </section>
  );
}

export function SimulationAssistant({ initialDraft, onApply, notify }) {
  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef(false);
  const current = draft || initialDraft?.draft || initialDraft;
  async function parse() {
    if (!prompt.trim() || requestRef.current) return;
    requestRef.current = true;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/plans/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompt }),
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(
          typeof data.detail === "string" ? data.detail : "参数草案未能生成。",
        );
      setDraft(data);
    } catch (error) {
      setError(error.message);
      notify?.(error.message);
    } finally {
      requestRef.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="simulation-assistant card-base">
      <div className="simulation-assistant-heading">
        <span>
          <MessageSquare size={16} />
          描述你的实验
        </span>
        <small>先整理参数，再检查计算计划</small>
      </div>
      <div className="simulation-prompt">
        <textarea
          aria-label="自然语言描述仿真参数"
          placeholder="例如：Munk 深海，频率50和100Hz，源深500m、接收深度1000m，距离1至50km。"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <button type="button" disabled={busy || !prompt.trim()} onClick={parse}>
          {busy ? (
            <Loader2 className="spin" size={16} />
          ) : (
            <ArrowRight size={16} />
          )}
          <span>{busy ? "正在解析" : "整理参数"}</span>
        </button>
      </div>
      {error && (
        <p className="draft-error" role="status">
          {error}
        </p>
      )}
      {current && <SimulationDraftCard draft={current} onApply={onApply} />}
    </section>
  );
}

const colors = ["#258cae", "#8e87c2", "#cf9a59", "#4caa9d"];
export function JobComparison({ ids, onClose }) {
  const [data, setData] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function compare() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/jobs/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "比较请求未完成。",
        );
      setData(result);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  const chart = useMemo(() => {
    if (!data?.series?.length) return null;
    const series = data.series.map((item) => ({
      ...item,
      points: (item.ranges_m || [])
        .map((range, index) => [
          Number(range) / 1000,
          Number(item.curve_tl_db?.[index]),
        ])
        .filter(
          ([x, y], index) =>
            item.curve_tl_db?.[index] != null &&
            Number.isFinite(x) &&
            Number.isFinite(y),
        ),
    }));
    const points = series.flatMap((item) => item.points);
    if (!points.length) return null;
    const xMin = Math.min(...points.map((p) => p[0])),
      xMax = Math.max(...points.map((p) => p[0])),
      rawMin = Math.min(...points.map((p) => p[1])),
      rawMax = Math.max(...points.map((p) => p[1]));
    const yMin = Math.floor(rawMin / 10) * 10,
      yMax = Math.max(yMin + 10, Math.ceil(rawMax / 10) * 10);
    return {
      series,
      xMin,
      xMax,
      yMin,
      yMax,
      x: (v) => 60 + ((v - xMin) / Math.max(1e-6, xMax - xMin)) * 670,
      y: (v) => 35 + ((v - yMin) / (yMax - yMin)) * 220,
    };
  }, [data]);
  return (
    <section className="job-comparison card-base" aria-label="计算结果对比">
      <header>
        <div>
          <span className="section-kicker">实验对照</span>
          <h2>比较 {ids.length} 组真实计算</h2>
        </div>
        <button type="button" onClick={onClose} aria-label="关闭结果对比">
          <X size={18} />
        </button>
      </header>
      {!data && (
        <div className="compare-start">
          <p>以结果 JSON 中的接收深度曲线核对，不根据图片反推数值。</p>
          <button type="button" disabled={busy} onClick={compare}>
            {busy && <Loader2 size={14} className="spin" />}
            {busy ? "正在读取结果" : "读取并比较结果"}
          </button>
        </div>
      )}
      {error && (
        <p className="draft-error" role="status">
          {error}
        </p>
      )}
      {data && (
        <>
          <div
            className={`compare-notice${data.comparable ? " comparable" : ""}`}
          >
            {data.comparable ? <Check size={15} /> : <FlaskConical size={15} />}
            <span>
              {data.comparable
                ? "已通过本次结果可比性检查"
                : "存在比较条件差异，请先核对下方说明"}
              ；不据此评价海域或环境优劣。
            </span>
          </div>
          {chart && (
            <div className="comparison-chart">
              <svg
                viewBox="0 0 780 310"
                role="img"
                aria-label="传播损失对比曲线，横轴距离km，纵轴传播损失dB"
              >
                {Array.from({ length: 5 }, (_, i) => {
                  const value =
                    chart.yMin + ((chart.yMax - chart.yMin) * i) / 4;
                  return (
                    <g key={i}>
                      <line
                        x1="60"
                        x2="730"
                        y1={chart.y(value)}
                        y2={chart.y(value)}
                        stroke="#e6eff4"
                      />
                      <text x="48" y={chart.y(value) + 4} textAnchor="end">
                        {value.toFixed(0)}
                      </text>
                    </g>
                  );
                })}
                {Array.from({ length: 6 }, (_, i) => {
                  const value =
                    chart.xMin + ((chart.xMax - chart.xMin) * i) / 5;
                  return (
                    <text
                      key={i}
                      x={chart.x(value)}
                      y="276"
                      textAnchor="middle"
                    >
                      {value.toFixed(1)}
                    </text>
                  );
                })}
                <text x="395" y="302" textAnchor="middle">
                  距离 / km
                </text>
                <text
                  x="14"
                  y="150"
                  transform="rotate(-90 14 150)"
                  textAnchor="middle"
                >
                  传播损失 / dB
                </text>
                {chart.series.map((series, index) => {
                  const step = Math.max(
                    1,
                    Math.ceil(series.points.length / 650),
                  );
                  return (
                    <polyline
                      key={series.id}
                      fill="none"
                      stroke={colors[index]}
                      strokeWidth="1.6"
                      points={series.points
                        .filter(
                          (_, i) =>
                            i % step === 0 || i === series.points.length - 1,
                        )
                        .map(([x, y]) => `${chart.x(x)},${chart.y(y)}`)
                        .join(" ")}
                    />
                  );
                })}
              </svg>
              <div className="comparison-legends">
                {chart.series.map((series, index) => (
                  <span key={series.id}>
                    <i style={{ background: colors[index] }} />
                    {series.frequency_hz} Hz · 源深 {series.source_depth_m} m ·
                    接收 {series.actual_receiver_depth_m} m
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="comparison-conditions">
            {[...(data.conditions || []), ...(data.warnings || [])].map(
              (item, index) => (
                <p key={index}>
                  {typeof item === "string"
                    ? item
                    : item.message || item.note || JSON.stringify(item)}
                </p>
              ),
            )}
            {data.pairs?.map((pair, index) => (
              <details key={index}>
                <summary>
                  {pair.left_id} ↔ {pair.right_id} ·{" "}
                  {pair.comparable && pair.single_factor_controlled
                    ? "单因素条件一致"
                    : "不可单因素归因"}
                </summary>
                <p>{pair.note}</p>
                <dl>
                  {Object.entries(pair.checks || {}).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>
                        {typeof value === "boolean"
                          ? value
                            ? "一致"
                            : "不一致"
                          : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </details>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
