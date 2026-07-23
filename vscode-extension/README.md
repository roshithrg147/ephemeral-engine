# SC-EVM Chat for VS Code

Native VS Code Chat participant for the local SC-EVM gateway.

## Run locally

1. Start the gateway from the repository root:

   ```bash
   uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
   ```

2. Build and install the extension:

   ```bash
   cd vscode-extension
   npm ci
   npm run package
   code --install-extension scevm-chat-0.3.0.vsix --force
   ```

3. Reload VS Code, open Chat, and enter:

   ```text
   @scevm Review the active module and propose the next implementation step.
   ```

Use `@scevm /diagnose`, `@scevm /status`, `@scevm /burn`, or `@scevm /new` for lifecycle controls.

Use `@scevm /review` for repository analysis. After one read approval, extension sends a bounded safe
file inventory plus core manifests. M2 can call `list_files` and `read_file` inside the agent loop,
then produce a plan from actual workspace evidence. Terminal-output requests are detected and
recovered automatically. User never needs to paste `ls`, `find`, or file contents.

## Agent edit loop

Default `confirmThenAutoApply` mode asks once for each chat request. After approval, structured
`save_file` actions from SC-EVM are applied and reported back to the same session so M1 and M2 can
continue. Read-only `list_files` and `read_file` actions use separate workspace-read approval. Loop
stops after eight iterations by default, on repeated actions, degraded output, conflicts,
unsupported actions, cancellation, or completion.

Set `scevm.executionMode` to `reviewEachEdit` to require a diff and confirmation for every edit.
Change `scevm.maxAgentIterations` to a value from 1 through 10. Shell commands and arbitrary process
execution remain unsupported. `scevm.developmentPhase` defaults to 3 for this completed backend;
lower it when working in an earlier architecture phase.

Every request includes authoritative VS Code workspace folder names and active-file identity, even
when no file content is shared. Gateway-local Graphify retrieval is disabled by default because its
index may describe the gateway repository instead of the open VS Code workspace. Enable
`scevm.graphifyEnabled` only when both indexes represent the same workspace.

Open **SC-EVM: Show Diagnostics** from Command Palette for connection, session, SSE event, TTFT, total
duration, action, and failure logs. Prompt content, workspace content, bearer tokens, and response
content are never written to this output channel.

## Security model

- Attached files are treated as explicitly approved context.
- Active-editor context requires one-time approval by default.
- `.env`, credential files, private keys, and secret-like lines are excluded or redacted.
- Context is bounded and must remain inside the open workspace.
- Remote gateways are disabled by default and require HTTPS when enabled.
- Bearer tokens are stored only in VS Code SecretStorage.
- Model commands are never executed.
- File writes must remain inside the workspace and cannot traverse symlinks.
- Files are rejected when they change between proposal and application.
- Auto-apply requires one explicit approval per request and stops on degraded model output.

Burn provides logical session and vector-state deletion; it is not physical RAM sanitization.
