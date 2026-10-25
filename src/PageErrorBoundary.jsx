import React from 'react';

export default class PageErrorBoundary extends React.Component {
 state={error:null};
 static getDerivedStateFromError(error){return {error}}
 render(){
  if(this.state.error)return <div className="empty panel" role="alert"><h2>当前页面暂时无法显示</h2><p>计算文件仍保留。页面版本可能已更新，请刷新后重试；也可以通过左侧栏目切换页面。</p><button className="button" onClick={()=>window.location.reload()}>刷新页面</button><details><summary>错误详情</summary><pre>{String(this.state.error.message||this.state.error)}</pre></details></div>;
  return this.props.children;
 }
}
