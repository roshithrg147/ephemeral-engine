import assert from "node:assert/strict";
import test from "node:test";

import {
  buildGroundedPrompt,
  isRepositoryReviewRequest,
  isWorkspaceDeflection,
} from "../grounding.js";

test("workspace scope is authoritative even without file context", () => {
  const prompt = buildGroundedPrompt(
    "Review the active module",
    [],
    { folders: ["customer-app"], activeFile: "src/service.ts" },
  );

  assert.match(prompt, /AUTHORITATIVE_VSCODE_WORKSPACE_SCOPE/);
  assert.match(prompt, /customer-app/);
  assert.match(prompt, /src\/service\.ts/);
  assert.match(prompt, /Never identify the gateway working directory/);
  assert.doesNotMatch(prompt, /BEGIN_APPROVED_WORKSPACE_CONTEXT_JSONL/);
});

test("approved context remains bounded by workspace identity", () => {
  const prompt = buildGroundedPrompt(
    "Review file",
    [{ path: "src/main.ts", content: "export {};", source: "attachment" }],
    { folders: ["customer-app"] },
  );

  assert.match(prompt, /BEGIN_APPROVED_WORKSPACE_CONTEXT_JSONL/);
  assert.match(prompt, /src\/main\.ts/);
});

test("repository review intent is detected without matching ordinary file questions", () => {
  assert.equal(isRepositoryReviewRequest("Review the entire project directory"), true);
  assert.equal(isRepositoryReviewRequest("Audit this codebase and create a plan"), true);
  assert.equal(isRepositoryReviewRequest("Explain this selected function"), false);
});

test("terminal-output chatbot deflection is detected", () => {
  assert.equal(
    isWorkspaceDeflection("Could you run these commands in your terminal and paste the output?"),
    true,
  );
  assert.equal(isWorkspaceDeflection("Repository has two services and needs auth next."), false);
});
