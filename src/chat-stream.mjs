/** Browser-native SSE reader. Also accepts the previous JSON chat protocol. */
export async function readChatResponse(
  response,
  { onStatus = () => {}, onDelta = () => {} } = {},
) {
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const error = new Error(
      typeof data?.detail === "string"
        ? data.detail
        : `服务请求未完成（HTTP ${response.status}）`,
    );
    error.status = response.status;
    error.code = data?.code;
    throw error;
  }
  if (!response.headers?.get("content-type")?.includes("text/event-stream")) {
    const result = await response.json();
    if (typeof result?.reply !== "string")
      throw new Error("服务没有返回完整的文字回答。");
    return result;
  }
  if (!response.body?.getReader) throw new Error("浏览器无法读取流式响应。");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "",
    done = null;
  const dispatch = (frame) => {
    let event = "message";
    const lines = [];
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:"))
        lines.push(line.slice(5).replace(/^ /, ""));
    }
    if (!lines.length) return;
    let data;
    try {
      data = JSON.parse(lines.join("\n"));
    } catch {
      throw new Error("流式响应格式不兼容，已保留收到的内容。");
    }
    if (event === "status") onStatus(data);
    else if (event === "delta" && typeof data.text === "string")
      onDelta(data.text);
    else if (event === "done") {
      if (typeof data.reply !== "string")
        throw new Error("流式响应缺少最终回答。");
      done = data;
    } else if (event === "error") {
      const error = new Error(
        typeof data.detail === "string" ? data.detail : "生成未完成。",
      );
      error.code = data.code;
      throw error;
    }
  };
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value || new Uint8Array(), {
        stream: !chunk.done,
      });
      let delimiter;
      while ((delimiter = /\r?\n\r?\n/.exec(buffer))) {
        dispatch(buffer.slice(0, delimiter.index));
        buffer = buffer.slice(delimiter.index + delimiter[0].length);
      }
      if (done) {
        await reader.cancel().catch(() => {});
        return done;
      }
      if (chunk.done) break;
    }
    if (buffer.trim()) dispatch(buffer);
    if (!done) {
      const error = new Error("连接在回答完成前结束，已保留收到的内容。");
      error.code = "STREAM_INCOMPLETE";
      throw error;
    }
    return done;
  } finally {
    reader.releaseLock();
  }
}
