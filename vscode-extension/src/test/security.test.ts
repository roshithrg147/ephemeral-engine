import assert from "node:assert/strict";
import * as fs from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import test from "node:test";

import {
  isBlockedContextPath,
  redactSecretLines,
  resolveWorkspacePath,
  validateGatewayUrl,
} from "../security.js";

test("gateway validation defaults to loopback and requires HTTPS remotely", () => {
  assert.equal(validateGatewayUrl("http://127.0.0.1:8000", false).hostname, "127.0.0.1");
  assert.throws(() => validateGatewayUrl("http://example.com", false), /disabled/);
  assert.throws(() => validateGatewayUrl("http://example.com", true), /HTTPS/);
  assert.equal(validateGatewayUrl("https://example.com", true).hostname, "example.com");
});

test("secret-bearing files and lines are blocked or redacted", () => {
  assert.equal(isBlockedContextPath("/workspace/.env"), true);
  assert.equal(isBlockedContextPath("/workspace/private.pem"), true);
  assert.equal(isBlockedContextPath("/workspace/src/main.ts"), false);
  assert.equal(
    redactSecretLines("name=test\nAPI_KEY=secret\nvalue=ok"),
    "name=test\n[REDACTED SECRET-LIKE LINE]\nvalue=ok",
  );
});

test("workspace path validation rejects traversal and symlinks", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "scevm-extension-"));
  const outside = await fs.mkdtemp(path.join(os.tmpdir(), "scevm-outside-"));
  try {
    assert.equal(await resolveWorkspacePath(root, "src/main.ts"), path.join(root, "src/main.ts"));
    await assert.rejects(resolveWorkspacePath(root, "../escape.ts"), /escapes/);
    await fs.symlink(outside, path.join(root, "linked"));
    await assert.rejects(resolveWorkspacePath(root, "linked/file.ts"), /symbolic link/);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
    await fs.rm(outside, { recursive: true, force: true });
  }
});
