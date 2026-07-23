import assert from "node:assert/strict";
import test from "node:test";

import { decodeSseData, SseDecoder } from "../sse.js";

test("SSE decoder emits multiline events and resets event names", () => {
  const decoder = new SseDecoder();
  assert.deepEqual(decoder.feedLine("event: response_content"), []);
  assert.deepEqual(decoder.feedLine('data: {"content":'), []);
  assert.deepEqual(decoder.feedLine('data: "hello"}'), []);
  const events = decoder.feedLine("");
  assert.deepEqual(events, [
    { event: "response_content", data: '{"content":\n"hello"}' },
  ]);
  assert.deepEqual(decodeSseData(events[0]?.data ?? ""), { content: "hello" });
});

test("SSE decoder ignores comments and preserves done markers", () => {
  const decoder = new SseDecoder();
  assert.deepEqual(decoder.feedLine(": heartbeat"), []);
  decoder.feedLine("event: done");
  decoder.feedLine("data: [DONE]");
  const events = decoder.finish();
  assert.equal(events[0]?.event, "done");
  assert.equal(decodeSseData(events[0]?.data ?? ""), "[DONE]");
});
