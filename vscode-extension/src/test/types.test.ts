import assert from "node:assert/strict";
import test from "node:test";

import {
  isListFilesAction,
  isReadFileAction,
  parseEngineAction,
} from "../types.js";

test("engine action parser accepts bounded read-only workspace tools", () => {
  const read = parseEngineAction({
    type: "read_file",
    payload: { file_path: "src/main.ts" },
  });
  assert.ok(read !== undefined && isReadFileAction(read));
  assert.equal(read.payload.file_path, "src/main.ts");

  const list = parseEngineAction({
    type: "list_files",
    payload: { glob: "src/**/*.ts", max_results: 50 },
  });
  assert.ok(list !== undefined && isListFilesAction(list));
  assert.equal(list.payload.glob, "src/**/*.ts");
  assert.equal(list.payload.max_results, 50);
});

test("engine action parser does not promote malformed read actions", () => {
  const malformed = parseEngineAction({ type: "read_file", payload: {} });
  assert.equal(malformed?.type, "read_file");
  assert.equal(isReadFileAction(malformed!), false);
});
