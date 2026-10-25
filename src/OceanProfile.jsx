import React from "react";
import guideImage from "./assets/ocean-assistant-v07.png";

// 侧栏课程项目名片。人物图同时供知识图谱 Banner 使用，
// 原先的 sakana-widget 动画组件已随浮动课程助手一并移除。
export default function OceanProfile() {
  return (
    <div className="ocean-profile card-base">
      <svg viewBox="0 0 240 154" fill="none" aria-hidden="true">
        <circle cx="190" cy="28" r="35" fill="#FFF6DF" />
        <path
          d="M0 60C40 39 65 74 107 58S174 37 240 60V154H0Z"
          fill="#C5EAF1"
        />
        <path
          d="M0 80C49 59 81 97 121 78S190 64 240 76V154H0Z"
          fill="#9BD6E6"
        />
        <path
          d="M0 104C53 81 81 124 131 105S194 95 240 105V154H0Z"
          fill="#79BBD4"
        />
        <path d="M11 49L71 30 59 46 40 46 29 52Z" fill="#fff" opacity=".8" />
        <path
          d="M18 126C57 115 88 138 130 126M8 139C47 128 83 151 125 140"
          stroke="#E8FAFC"
          strokeWidth="2"
        />
      </svg>
      <img src={guideImage} alt="原创海洋研究员" />
      <div>
        <span>NPU · 西北工业大学</span>
        <strong>向海而行</strong>
        <small>公诚勇毅 · 课程研究空间</small>
      </div>
    </div>
  );
}

export { guideImage };
