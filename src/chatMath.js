// Normalize model LaTeX delimiters before Markdown consumes their backslashes.
// Preserve fenced and inline code verbatim.
export function normalizeChatMath(text) {
  return text.split(/(`{3,}[^\n]*\n[\s\S]*?\n`{3,}|~{3,}[^\n]*\n[\s\S]*?\n~{3,}|`+[^\n]*?`+)/g).map((part,i)=>{
    if(i%2) return part;
    return part
      .replace(/\\\[([\s\S]*?)\\\]/g,(_,math)=>'\n\n$$\n'+math.trim()+'\n$$\n\n')
      .replace(/\\\(([\s\S]*?)\\\)/g,(_,math)=>'$'+math.trim()+'$')
      .replace(/\$\$([\s\S]*?)\$\$/g,(_,math)=>'\n\n$$\n'+math.trim()+'\n$$\n\n');
  }).join('');
}
