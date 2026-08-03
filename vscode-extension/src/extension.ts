import * as vscode from "vscode";

import {
  ActionLoopGuard,
  buildToolContinuation,
  buildWorkspaceToolContinuation,
} from "./agent_loop.js";
import { ScevmClient } from "./client.js";
import { ContextCollector } from "./context.js";
import { PendingEditManager, PreviewProvider } from "./edits.js";
import {
  buildGroundedPrompt,
  isRepositoryReviewRequest,
  isWorkspaceDeflection,
} from "./grounding.js";
import { validateGatewayUrl } from "./security.js";
import {
  isListFilesAction,
  isReadFileAction,
  isSaveFileAction,
  type StreamEvent,
  type WorkspaceScope,
} from "./types.js";
import { WorkspaceToolService } from "./workspace_tools.js";

const TOKEN_SECRET_KEY = "scevm.oidcBearerToken";

type ContextPolicy = "prompt" | "attachmentsOnly" | "none";
type ExecutionMode = "reviewEachEdit" | "confirmThenAutoApply";

class ExtensionRuntime implements vscode.Disposable {
  private client: ScevmClient | undefined;
  private readonly collector = new ContextCollector();
  private readonly workspaceTools = new WorkspaceToolService();
  private readonly disposables: vscode.Disposable[] = [];
  private disposed = false;

  public constructor(
    private readonly extensionContext: vscode.ExtensionContext,
    private readonly edits: PendingEditManager,
    private readonly output: vscode.OutputChannel,
  ) {}

  public register(): void {
    const participant = vscode.chat.createChatParticipant("scevm.chat", this.handleChat.bind(this));
    participant.iconPath = new vscode.ThemeIcon("server-process");
    this.disposables.push(
      participant,
      vscode.commands.registerCommand("scevm.openChat", async () => {
        await vscode.commands.executeCommand("workbench.action.chat.open", {
          query: "@scevm ",
        });
      }),
      vscode.commands.registerCommand("scevm.setToken", async () => {
        const token = await vscode.window.showInputBox({
          title: "SC-EVM OIDC bearer token",
          prompt: "Stored in VS Code SecretStorage. Submit empty input to remove it.",
          password: true,
          ignoreFocusOut: true,
        });
        if (token === undefined) {
          return;
        }
        await this.disposeClient();
        if (token.length === 0) {
          await this.extensionContext.secrets.delete(TOKEN_SECRET_KEY);
          void vscode.window.showInformationMessage("SC-EVM bearer token removed.");
        } else {
          await this.extensionContext.secrets.store(TOKEN_SECRET_KEY, token);
          void vscode.window.showInformationMessage("SC-EVM bearer token stored securely.");
        }
      }),
      vscode.commands.registerCommand("scevm.burnSession", async () => {
        const verified = await this.burnSession();
        void vscode.window.showInformationMessage(
          verified ? "SC-EVM session burn verified." : "SC-EVM session burn was not verified.",
        );
      }),
      vscode.commands.registerCommand("scevm.showDiagnostics", () => {
        this.output.show(true);
      }),
      vscode.commands.registerCommand("scevm.applyPendingEdit", async (id: unknown) => {
        if (typeof id !== "string") {
          throw new Error("Invalid SC-EVM edit identifier");
        }
        await this.edits.reviewAndApply(id);
      }),
      vscode.workspace.onDidChangeConfiguration(async (event) => {
        if (event.affectsConfiguration("scevm")) {
          await this.disposeClient();
        }
      }),
    );
  }

  public async dispose(): Promise<void> {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    await this.disposeClient();
    for (const disposable of this.disposables) {
      disposable.dispose();
    }
  }

  private async handleChat(
    request: vscode.ChatRequest,
    _context: vscode.ChatContext,
    response: vscode.ChatResponseStream,
    token: vscode.CancellationToken,
  ): Promise<vscode.ChatResult> {
    try {
      const client = await this.getClient();
      this.log("chat.request", `command=${request.command ?? "chat"}`);
      if (request.command === "status") {
        await client.health();
        response.markdown(
          `SC-EVM gateway is ready. Active session: \`${client.activeSessionId}\`. Models: Nemotron (M1) and GPT-OSS (M2).`,
        );
        return { metadata: { status: "ready" } };
      }
      if (request.command === "burn") {
        const verified = await this.burnSession();
        response.markdown(verified ? "Session burn verified." : "Session burn could not be verified.");
        return { metadata: { burnVerified: verified } };
      }
      if (request.command === "new") {
        await client.newSession();
        response.markdown(`Started fresh session \`${client.activeSessionId}\`.`);
        return { metadata: { status: "newSession" } };
      }
      if (request.command === "diagnose") {
        await client.health();
        const configuration = vscode.workspace.getConfiguration("scevm");
        response.markdown(
          [
            "SC-EVM diagnostic passed.",
            `Gateway: \`${configuration.get<string>("gatewayUrl", "http://127.0.0.1:8000")}\``,
            `Session: \`${client.activeSessionId}\``,
            "Pipeline: Nemotron (M1) → GPT-OSS (M2) → VS Code Chat",
            `Execution: \`${configuration.get<ExecutionMode>("executionMode", "confirmThenAutoApply")}\``,
            `Development phase: \`${configuration.get<number>("developmentPhase", 3)}\``,
          ].join("\n\n"),
        );
        return { metadata: { status: "diagnosticReady" } };
      }
      const userPrompt =
        request.command === "review" && request.prompt.trim().length === 0
          ? "Review the entire active workspace. Identify modules, current implementation state, risks, and the next evidence-backed development steps."
          : request.prompt.trim();
      if (userPrompt.length === 0) {
        return { errorDetails: { message: "Enter a development request for @scevm." } };
      }

      const configuration = vscode.workspace.getConfiguration("scevm");
      await client.health();
      response.progress("SC-EVM gateway ready.");
      const policy = configuration.get<ContextPolicy>("contextPolicy", "prompt");
      const maxBytes = configuration.get<number>("maxContextBytes", 65_536);
      const executionMode = configuration.get<ExecutionMode>(
        "executionMode",
        "confirmThenAutoApply",
      );
      const configuredIterations = configuration.get<number>("maxAgentIterations", 8);
      const maxIterations = Math.max(1, Math.min(10, Math.trunc(configuredIterations)));
      const workspaceScope = this.collector.describeWorkspace();
      this.log(
        "workspace.scope",
        `folders=${workspaceScope.folders.join(",")} active=${workspaceScope.activeFile ?? "none"}`,
      );
      const repositoryReview =
        request.command === "review" || isRepositoryReviewRequest(userPrompt);
      const contexts = await this.collector.collect(
        request,
        repositoryReview && policy !== "none" ? "attachmentsOnly" : policy,
        maxBytes,
      );
      let workspaceReadApproved = false;
      if (repositoryReview && policy !== "none") {
        workspaceReadApproved = await this.requestWorkspaceReadApproval(workspaceScope);
        if (!workspaceReadApproved) {
          response.markdown(
            "\n\n> Workspace review cancelled. SC-EVM did not inspect repository files.",
          );
          return { metadata: { status: "workspaceReviewCancelled" } };
        }
        const usedBytes = contexts.reduce(
          (total, context) => total + Buffer.byteLength(context.content, "utf8"),
          0,
        );
        const remainingBytes = Math.max(0, maxBytes - usedBytes);
        const reviewContexts =
          remainingBytes === 0
            ? []
            : await this.workspaceTools.buildReviewContexts(workspaceScope, remainingBytes);
        contexts.push(...reviewContexts);
        response.progress(
          `Workspace inventory approved: ${reviewContexts.length} context blocks.`,
        );
        this.log("workspace.inventory", `contexts=${reviewContexts.length}`);
      }
      for (const context of contexts) {
        response.progress(`Approved context: ${context.path}`);
      }
      let prompt = buildGroundedPrompt(userPrompt, contexts, workspaceScope);
      let appliedEdits = 0;
      let workspaceReads = 0;
      let autoApplyApproved = false;
      const loopGuard = new ActionLoopGuard();
      for (let iteration = 1; iteration <= maxIterations; iteration += 1) {
        response.progress(`M1 → M2 iteration ${iteration}/${maxIterations}`);
        let proposedAction: StreamEvent & { kind: "action" } | undefined;
        let degraded = false;
        let contentSeen = false;
        let iterationContent = "";
        for await (const event of client.query(prompt, token)) {
          if (event.kind === "action") {
            proposedAction = event;
            continue;
          }
          if (event.kind === "warning") {
            degraded = true;
          }
          if (event.kind === "content") {
            contentSeen = true;
            iterationContent += event.content;
            continue;
          }
          await this.renderEvent(event, response);
        }
        if (!contentSeen) {
          throw new Error("SC-EVM completed without user-facing response content");
        }
        if (proposedAction === undefined) {
          if (
            repositoryReview &&
            workspaceReadApproved &&
            isWorkspaceDeflection(iterationContent) &&
            iteration < maxIterations
          ) {
            const recoveryAction = {
              type: "list_files",
              payload: { glob: "**/*", max_results: 1000 },
            } as const;
            loopGuard.assertNew(recoveryAction);
            const toolResult = await this.workspaceTools.executeList(recoveryAction);
            workspaceReads += 1;
            this.log("workspace.deflection_recovered", `iteration=${iteration}`);
            response.progress("Recovered chatbot deflection with approved workspace inventory.");
            prompt = buildWorkspaceToolContinuation(toolResult, workspaceScope);
            continue;
          }
          response.markdown(iterationContent);
          break;
        }
        if (degraded) {
          response.markdown(iterationContent);
          response.markdown(
            "\n\n> Degraded model output cannot use workspace tools or modify workspace. Retry after Model 2 recovers.",
          );
          break;
        }
        if (
          isReadFileAction(proposedAction.action) ||
          isListFilesAction(proposedAction.action)
        ) {
          if (policy === "none") {
            response.markdown(iterationContent);
            response.markdown(
              "\n\n> Workspace tool blocked because `scevm.contextPolicy` is `none`.",
            );
            break;
          }
          if (!workspaceReadApproved) {
            workspaceReadApproved = await this.requestWorkspaceReadApproval(workspaceScope);
            if (!workspaceReadApproved) {
              response.markdown(iterationContent);
              response.markdown("\n\n> Workspace inspection was not approved.");
              break;
            }
          }
          loopGuard.assertNew(proposedAction.action);
          const toolResult = isReadFileAction(proposedAction.action)
            ? await this.workspaceTools.executeRead(proposedAction.action)
            : await this.workspaceTools.executeList(proposedAction.action);
          workspaceReads += 1;
          this.log("workspace.tool", `tool=${toolResult.label} iteration=${iteration}`);
          response.progress(`Workspace tool completed: ${toolResult.label}`);
          if (iteration === maxIterations) {
            response.markdown(iterationContent);
            response.markdown(
              `\n\n> Agent loop reached ${maxIterations} iterations after ${toolResult.label}.`,
            );
            break;
          }
          prompt = buildWorkspaceToolContinuation(toolResult, workspaceScope);
          continue;
        }
        if (!isSaveFileAction(proposedAction.action)) {
          response.markdown(iterationContent);
          response.markdown(
            `\n\n> Proposed \`${proposedAction.action.type}\` action was not executed. Allowed actions: list_files, read_file, save_file.`,
          );
          break;
        }
        response.markdown(iterationContent);
        loopGuard.assertNew(proposedAction.action);
        const edit = await this.edits.queue(proposedAction.action);
        if (executionMode === "reviewEachEdit") {
          this.renderReviewButton(edit, response);
          break;
        }
        if (!autoApplyApproved) {
          const decision = await vscode.window.showWarningMessage(
            "Allow SC-EVM to apply workspace file edits and continue this request?",
            {
              modal: true,
              detail: `Maximum ${maxIterations} M1 → M2 iterations. Commands are never executed. Changed files are checked for conflicts and workspace escape.`,
            },
            "Allow This Request",
          );
          if (decision !== "Allow This Request") {
            this.renderReviewButton(edit, response);
            break;
          }
          autoApplyApproved = true;
        }
        await this.edits.applyAuthorized(edit.id);
        appliedEdits += 1;
        this.log("action.applied", `path=${edit.relativePath} iteration=${iteration}`);
        response.progress(`Applied workspace edit: ${edit.relativePath}`);
        if (iteration === maxIterations) {
          response.markdown(
            `\n\n> Agent loop reached ${maxIterations} iterations after applying ${edit.relativePath}.`,
          );
          break;
        }
        prompt = buildToolContinuation(edit.relativePath);
      }
      return {
        metadata: {
          sessionId: client.activeSessionId,
          contextFiles: contexts.length,
          workspaceReads,
          appliedEdits,
        },
      };
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unknown SC-EVM extension error";
      this.log("chat.failed", message);
      response.markdown(`\n\n> SC-EVM error: \`${escapeInlineCode(message)}\``);
      response.button({
        command: "scevm.showDiagnostics",
        title: "Show SC-EVM Diagnostics",
      });
      return { errorDetails: { message } };
    }
  }

  private async renderEvent(
    event: StreamEvent,
    response: vscode.ChatResponseStream,
  ): Promise<void> {
    switch (event.kind) {
      case "content":
        response.markdown(event.content);
        return;
      case "progress":
        response.progress(event.message);
        return;
      case "usage":
        response.progress(`Usage: M1 ${String(event.model1)}, M2 ${String(event.model2)}`);
        return;
      case "warning":
        response.markdown(`\n\n> ⚠️ ${event.message}`);
        return;
      case "action":
        return;
    }
  }

  private async getClient(): Promise<ScevmClient> {
    if (this.client !== undefined) {
      return this.client;
    }
    const configuration = vscode.workspace.getConfiguration("scevm");
    const gateway = validateGatewayUrl(
      configuration.get<string>("gatewayUrl", "http://127.0.0.1:8000"),
      configuration.get<boolean>("allowRemoteGateway", false),
    );
    const bearerToken = await this.extensionContext.secrets.get(TOKEN_SECRET_KEY);
    this.client = new ScevmClient({
      gateway,
      timeoutSeconds: configuration.get<number>("requestTimeoutSeconds", 180),
      graphifyEnabled: configuration.get<boolean>("graphifyEnabled", false),
      developmentPhase: Math.max(
        0,
        Math.min(3, Math.trunc(configuration.get<number>("developmentPhase", 3))),
      ),
      onDiagnostic: (event, detail) => {
        this.log(event, detail);
      },
      onAuthFailure: async () => {
        // Attempt local secret read first
        const existing = await this.extensionContext.secrets.get(TOKEN_SECRET_KEY);
        if (existing) return existing;

        // Optional auto-login flow for development mode using backend /api/auth/login
        const allowAuto = configuration.get<boolean>("autoLogin", true);
        if (!allowAuto) return null;

        try {
          const email = configuration.get<string>("defaultEmail", "vscode-extension@local");
          const resp = await fetch(new URL("/api/auth/login", gateway).toString(), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
          });
          if (!resp.ok) return null;
          const payload = await resp.json();
          const token = payload?.data?.access_token;
          if (typeof token === "string" && token.length > 0) {
            await this.extensionContext.secrets.store(TOKEN_SECRET_KEY, token);
            void vscode.window.showInformationMessage("SC-EVM: obtained development bearer token");
            return token;
          }
        } catch (err) {
          this.log("auth.autologin.failed", String(err));
        }
        return null;
      },
      ...(bearerToken === undefined ? {} : { bearerToken }),
    });
    return this.client;
  }

  private async attemptAutoLogin(gateway: URL): Promise<string | null> {
    const configuration = vscode.workspace.getConfiguration("scevm");
    const email = configuration.get<string>("defaultEmail", "vscode-extension@local");
    try {
      const resp = await fetch(new URL("/api/auth/login", gateway).toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!resp.ok) return null;
      const payload = await resp.json();
      const token = payload?.data?.access_token;
      if (typeof token === "string" && token.length > 0) {
        await this.extensionContext.secrets.store(TOKEN_SECRET_KEY, token);
        return token;
      }
    } catch (err) {
      this.log("auth.autologin.failed", String(err));
    }
    return null;
  }

  private async burnSession(): Promise<boolean> {
    if (this.client === undefined) {
      return true;
    }
    return this.client.burn();
  }

  private async disposeClient(): Promise<void> {
    if (this.client === undefined) {
      return;
    }
    try {
      await this.client.burn();
    } catch {
      // Deactivation cannot safely block VS Code shutdown; the gateway TTL remains the fallback.
    } finally {
      this.client = undefined;
    }
  }

  private renderReviewButton(
    edit: Awaited<ReturnType<PendingEditManager["queue"]>>,
    response: vscode.ChatResponseStream,
  ): void {
    response.button({
      command: "scevm.applyPendingEdit",
      title: `Review and Apply ${edit.relativePath}`,
      arguments: [edit.id],
    });
  }

  private async requestWorkspaceReadApproval(scope: WorkspaceScope): Promise<boolean> {
    const decision = await vscode.window.showInformationMessage(
      `Allow SC-EVM to inspect approved files in ${scope.folders.join(", ")} for this request?`,
      {
        modal: true,
        detail:
          "File names, core project manifests, and model-requested source files may be shared with the local gateway. Secrets, vendor trees, build output, binaries, oversized files, traversal, and symlinks are blocked.",
      },
      "Allow Workspace Review",
    );
    return decision === "Allow Workspace Review";
  }

  private log(event: string, detail?: string): void {
    const suffix = detail === undefined ? "" : ` ${detail}`;
    this.output.appendLine(`${new Date().toISOString()} ${event}${suffix}`);
  }
}

let runtime: ExtensionRuntime | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel("SC-EVM", { log: true });
  const previewProvider = new PreviewProvider();
  const edits = new PendingEditManager(previewProvider);
  runtime = new ExtensionRuntime(context, edits, output);
  runtime.register();
  output.info("extension.activated");
  context.subscriptions.push(
    output,
    vscode.workspace.registerTextDocumentContentProvider("scevm-preview", previewProvider),
    runtime,
  );
}

export async function deactivate(): Promise<void> {
  await runtime?.dispose();
  runtime = undefined;
}

function escapeInlineCode(value: string): string {
  return value.replaceAll("`", "'");
}
