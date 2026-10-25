import React from "react";
import { guideImage } from "./OceanProfile";

/** Original course artwork; not an official university platform. */
export default function OceanBanner({
  chapters = 6,
  nodes = 46,
  relations = null,
}) {
  return (
    <section
      className="ocean-banner anime-ocean-banner card-base"
      aria-label="海洋声学课程知识图谱"
    >
      <div className="ocean-banner-copy">
        <div className="ocean-school-line">
          <span className="ocean-npu-mark">NPU</span>
          <span>西北工业大学 · 四人小组课程项目</span>
        </div>
        <h1>海洋声学知识图谱</h1>
        <p>从知识点出发，查阅原理、证据与关联实验。</p>
        <div className="ocean-banner-caption">
          <span>{chapters} 个课程单元</span>
          <i />
          <span>{nodes} 个知识点</span>
          <i />
          <span>{relations ?? "—"} 条关系</span>
        </div>
      </div>
      <svg
        className="anime-banner-wave"
        viewBox="0 0 600 170"
        fill="none"
        aria-hidden="true"
      >
        <circle cx="470" cy="55" r="68" fill="#EAF8FC" />
        <circle
          cx="465"
          cy="62"
          r="57"
          stroke="#B7DEEB"
          strokeDasharray="3 8"
        />
        <path
          d="M0 123C76 81 113 167 196 119S320 91 394 124 531 105 600 123V170H0Z"
          fill="#CDEAF3"
        />
        <path
          d="M0 145C70 115 136 171 216 142S338 127 420 148 525 128 600 143V170H0Z"
          fill="#A9D8E8"
        />
        <path
          d="M48 107L86 96 112 107M80 82L110 74 136 82"
          stroke="#8ABBD0"
          strokeWidth="1.5"
        />
        <path d="M335 89H395L382 104H347Z" fill="#648FAA" />
        <path d="M355 72H375V89H355Z" fill="#fff" stroke="#648FAA" />
        <path d="M363 72V62M372 72V67" stroke="#648FAA" />
      </svg>
      <img
        className="anime-banner-guide"
        src={guideImage}
        alt="原创海洋研究员，手持水听器"
      />
      <span className="banner-course-note">公诚勇毅 · 课程作业</span>
    </section>
  );
}
