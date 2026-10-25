export function serializeChat(messages,format,exportedAt=new Date().toISOString()) {
  if(format==='json') return JSON.stringify({title:'海洋声学工作台聊天记录',exported_at:exportedAt,messages:messages.map(({role,text,created})=>({role,text,...(created?{created}: {})}))},null,2);
  const markdown=format==='md';
  const heading=markdown?'# 海洋声学工作台聊天记录':'海洋声学工作台聊天记录';
  return `${heading}\n\n导出时间：${exportedAt}\n消息数：${messages.length}\n\n`+messages.map(m=>`${markdown?'## ':''}${m.role==='assistant'?'海洋声学助手':'你'}${m.created?' · '+m.created:''}\n\n${m.text}`).join(markdown?'\n\n---\n\n':'\n\n────────────────────\n\n')+'\n';
}
