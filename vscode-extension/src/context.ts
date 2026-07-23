import { Buffer } from "node:buffer";
import * as path from "node:path";
import * as vscode from "vscode";

import { isBlockedContextPath, redactSecretLines } from "./security.js";
import type { ApprovedContext, WorkspaceScope } from "./types.js";

type ContextPolicy = "prompt" | "attachmentsOnly" | "none";

export class ContextCollector {
  public describeWorkspace(): WorkspaceScope {
    const folders = vscode.workspace.workspaceFolders;
    if (folders === undefined || folders.length === 0) {
      throw new Error("Open a VS Code folder or workspace before using @scevm");
    }
    const activeUri = vscode.window.activeTextEditor?.document.uri;
    const activeFolder =
      activeUri === undefined ? undefined : vscode.workspace.getWorkspaceFolder(activeUri);
    const activeFile =
      activeUri === undefined || activeFolder === undefined
        ? undefined
        : this.scopedPath(activeFolder, activeUri, folders.length > 1);
    return {
      folders: folders.map((folder) => folder.name),
      ...(activeFile === undefined ? {} : { activeFile }),
    };
  }

  public async collect(
    request: vscode.ChatRequest,
    policy: ContextPolicy,
    maxBytes: number,
  ): Promise<ApprovedContext[]> {
    if (policy === "none") {
      return [];
    }

    const contexts: ApprovedContext[] = [];
    const seen = new Set<string>();
    let remaining = maxBytes;
    for (const reference of request.references) {
      const location = this.referenceLocation(reference.value);
      if (location === undefined || seen.has(location.uri.toString())) {
        continue;
      }
      const context = await this.readApprovedLocation(location, "attachment", remaining);
      if (context !== undefined) {
        contexts.push(context);
        seen.add(location.uri.toString());
        remaining -= Buffer.byteLength(context.content, "utf8");
      }
      if (remaining <= 0) {
        return contexts;
      }
    }

    if (policy !== "prompt") {
      return contexts;
    }
    const editor = vscode.window.activeTextEditor;
    if (editor === undefined || seen.has(editor.document.uri.toString())) {
      return contexts;
    }
    const choice = await vscode.window.showInformationMessage(
      `Share ${this.displayPath(editor.document.uri)} with SC-EVM for this request?`,
      { modal: true, detail: "Secret-like lines are redacted. The approval applies once." },
      "Share Once",
      "Prompt Only",
    );
    if (choice !== "Share Once") {
      return contexts;
    }
    const range = editor.selection.isEmpty ? undefined : editor.selection;
    const context = await this.readApprovedLocation(
      new vscode.Location(editor.document.uri, range ?? this.fullDocumentRange(editor.document)),
      "activeEditor",
      remaining,
    );
    if (context !== undefined) {
      contexts.push(context);
    }
    return contexts;
  }

  private referenceLocation(value: unknown): vscode.Location | undefined {
    if (value instanceof vscode.Location) {
      return value;
    }
    if (value instanceof vscode.Uri) {
      return new vscode.Location(value, new vscode.Position(0, 0));
    }
    return undefined;
  }

  private async readApprovedLocation(
    location: vscode.Location,
    source: ApprovedContext["source"],
    remainingBytes: number,
  ): Promise<ApprovedContext | undefined> {
    const uri = location.uri;
    if (uri.scheme !== "file" || vscode.workspace.getWorkspaceFolder(uri) === undefined) {
      return undefined;
    }
    if (isBlockedContextPath(uri.fsPath) || remainingBytes <= 0) {
      void vscode.window.showWarningMessage(`SC-EVM did not share protected file ${uri.fsPath}`);
      return undefined;
    }

    if (source === "attachment") {
      const metadata = await vscode.workspace.fs.stat(uri);
      if (metadata.size > remainingBytes) {
        void vscode.window.showWarningMessage(
          `SC-EVM did not share ${this.displayPath(uri)} because it exceeds the remaining context limit. Select a smaller range instead.`,
        );
        return undefined;
      }
    }

    const document = await vscode.workspace.openTextDocument(uri);
    const requestedRange = location.range;
    const hasExplicitRange = !requestedRange.isEmpty;
    const raw = hasExplicitRange ? document.getText(requestedRange) : document.getText();
    const redacted = redactSecretLines(raw);
    const bounded = Buffer.from(redacted, "utf8").subarray(0, remainingBytes).toString("utf8");
    return {
      path: this.displayPath(uri),
      content: bounded,
      source,
    };
  }

  private fullDocumentRange(document: vscode.TextDocument): vscode.Range {
    const finalLine = document.lineAt(Math.max(0, document.lineCount - 1));
    return new vscode.Range(new vscode.Position(0, 0), finalLine.range.end);
  }

  private displayPath(uri: vscode.Uri): string {
    const folder = vscode.workspace.getWorkspaceFolder(uri);
    if (folder === undefined) {
      return path.basename(uri.fsPath);
    }
    return this.scopedPath(folder, uri, (vscode.workspace.workspaceFolders?.length ?? 0) > 1);
  }

  private scopedPath(
    folder: vscode.WorkspaceFolder,
    uri: vscode.Uri,
    includeFolder: boolean,
  ): string {
    const relative = path.relative(folder.uri.fsPath, uri.fsPath).split(path.sep).join("/");
    return includeFolder ? `${folder.name}/${relative}` : relative;
  }
}
