import assert from 'node:assert/strict';
import {serializeChat} from '../src/chatExport.js';
const messages=[{role:'user',text:'问题\n中文公式 x²',created:'2026-10-10'},{role:'assistant',text:'回答\n[source](http://localhost/source)'}];
const json=JSON.parse(serializeChat(messages,'json','test-time'));
assert.deepEqual(json.messages,messages);
assert.equal(json.exported_at,'test-time');
for(const format of ['md','txt']){
  const result=serializeChat(messages,format,'test-time');
  assert.ok(result.indexOf(messages[0].text)<result.indexOf(messages[1].text));
  assert.ok(result.includes('消息数：2'));
}
assert.ok(serializeChat(messages,'md').includes('## 海洋声学助手'));
assert.ok(!serializeChat(messages,'txt').includes('## 海洋声学助手'));
console.log('PASS: all export formats preserve Chinese, newlines, order and source links');
