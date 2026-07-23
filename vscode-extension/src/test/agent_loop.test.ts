import assert from "node:assert/strict";
import test from "node:test";

import { ActionLoopGuard, buildToolContinuation } from "../agent_loop.js";
import type { SaveFileAction } from "../types.js";

function saveFile(path: string, content: string): SaveFileAction {
  return {
    type: "save_file",
    payload: { file_path: path, file_content: content },
  };
}

test("action loop rejects an identical repeated edit", () => {
  const guard = new ActionLoopGuard();
  const action = saveFile("src/main.ts", "export {};\n");
  guard.assertNew(action);
  assert.throws(() => guard.assertNew(action), /repeated an identical workspace action/);
});

test("action loop allows a changed follow-up edit", () => {
  const guard = new ActionLoopGuard();
  guard.assertNew(saveFile("src/main.ts", "first"));
  assert.doesNotThrow(() => guard.assertNew(saveFile("src/main.ts", "second")));
});

test("continuation prompt reports only trusted tool result", () => {
  const prompt = buildToolContinuation("src/main.ts");
  assert.match(prompt, /save_file completed successfully/);
  assert.match(prompt, /Never repeat a completed edit/);
});
