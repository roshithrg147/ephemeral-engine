import * as path from "node:path";
import * as vscode from "vscode";

import { resolveWorkspacePath } from "./security.js";
import type { SaveFileAction } from "./types.js";

type PendingEdit = Readonly<{
  id: string;
  target: vscode.Uri;
  content: string;
  relativePath: string;
  workspaceRelativePath: string;
  original: FileSnapshot;
}>;

type FileSnapshot = Readonly<{ exists: boolean; content: string }>;

export class PreviewProvider implements vscode.TextDocumentContentProvider {
  private readonly contents = new Map<string, string>();

  public provideTextDocumentContent(uri: vscode.Uri): string {
    return this.contents.get(uri.toString()) ?? "";
  }

  public set(uri: vscode.Uri, content: string): void {
    this.contents.set(uri.toString(), content);
  }

  public delete(uri: vscode.Uri): void {
    this.contents.delete(uri.toString());
  }
}

export class PendingEditManager {
  private readonly pending = new Map<string, PendingEdit>();

  public constructor(private readonly previews: PreviewProvider) {}

  public async queue(action: SaveFileAction): Promise<PendingEdit> {
    if (Buffer.byteLength(action.payload.file_content, "utf8") > 2 * 1024 * 1024) {
      throw new Error("Proposed edit exceeds the 2 MiB safety limit");
    }
    const { folder, requestedPath } = this.selectWorkspaceFolder(action.payload.file_path);
    const resolved = await resolveWorkspacePath(folder.uri.fsPath, requestedPath);
    const target = vscode.Uri.file(resolved);
    const workspaceRelativePath = path.relative(folder.uri.fsPath, resolved);
    const displayRelativePath = workspaceRelativePath.split(path.sep).join("/");
    const relativePath =
      (vscode.workspace.workspaceFolders?.length ?? 0) > 1
        ? `${folder.name}/${displayRelativePath}`
        : displayRelativePath;
    const edit = {
      id: crypto.randomUUID(),
      target,
      content: action.payload.file_content,
      relativePath,
      workspaceRelativePath,
      original: await this.readSnapshot(target),
    } satisfies PendingEdit;
    this.pending.set(edit.id, edit);
    return edit;
  }

  public async reviewAndApply(id: string): Promise<boolean> {
    const edit = this.pending.get(id);
    if (edit === undefined) {
      void vscode.window.showWarningMessage("This SC-EVM edit is no longer available.");
      return false;
    }
    const oldUri = vscode.Uri.parse(`scevm-preview:before/${encodeURIComponent(edit.id)}`);
    const newUri = vscode.Uri.parse(`scevm-preview:after/${encodeURIComponent(edit.id)}`);
    this.previews.set(oldUri, edit.original.content);
    this.previews.set(newUri, edit.content);
    await vscode.commands.executeCommand(
      "vscode.diff",
      oldUri,
      newUri,
      `SC-EVM Review: ${edit.relativePath}`,
      { preview: true },
    );
    const answer = await vscode.window.showWarningMessage(
      `Apply the reviewed SC-EVM edit to ${edit.relativePath}?`,
      { modal: true, detail: "This changes your workspace. Cancel leaves the file untouched." },
      "Apply Edit",
    );
    if (answer !== "Apply Edit") {
      this.previews.delete(oldUri);
      this.previews.delete(newUri);
      return false;
    }
    const applied = await this.applyAuthorized(id, true);
    this.previews.delete(oldUri);
    this.previews.delete(newUri);
    return applied;
  }

  public async applyAuthorized(id: string, reveal = false): Promise<boolean> {
    const edit = this.pending.get(id);
    if (edit === undefined) {
      throw new Error("This SC-EVM edit is no longer available");
    }
    const folder = vscode.workspace.getWorkspaceFolder(edit.target);
    if (folder === undefined) {
      throw new Error("The proposed edit target is no longer in an open workspace");
    }
    const revalidated = await resolveWorkspacePath(folder.uri.fsPath, edit.workspaceRelativePath);
    if (revalidated !== edit.target.fsPath) {
      throw new Error("The proposed edit target changed after review");
    }
    const current = await this.readSnapshot(edit.target);
    if (
      current.exists !== edit.original.exists ||
      current.content !== edit.original.content
    ) {
      throw new Error(`Workspace file changed after SC-EVM proposed ${edit.relativePath}`);
    }
    await vscode.workspace.fs.createDirectory(vscode.Uri.file(path.dirname(edit.target.fsPath)));
    const workspaceEdit = new vscode.WorkspaceEdit();
    if (current.exists) {
      const document = await vscode.workspace.openTextDocument(edit.target);
      const finalLine = document.lineAt(Math.max(0, document.lineCount - 1));
      workspaceEdit.replace(
        edit.target,
        new vscode.Range(new vscode.Position(0, 0), finalLine.range.end),
        edit.content,
      );
    } else {
      workspaceEdit.createFile(edit.target, { overwrite: false, ignoreIfExists: false });
      workspaceEdit.insert(edit.target, new vscode.Position(0, 0), edit.content);
    }
    const applied = await vscode.workspace.applyEdit(workspaceEdit);
    if (!applied) {
      throw new Error("VS Code rejected the workspace edit");
    }
    this.pending.delete(id);
    if (reveal) {
      await vscode.window.showTextDocument(edit.target, { preview: false });
    }
    return true;
  }

  private async readSnapshot(uri: vscode.Uri): Promise<FileSnapshot> {
    const openDocument = vscode.workspace.textDocuments.find(
      (document) => document.uri.toString() === uri.toString(),
    );
    if (openDocument !== undefined) {
      return { exists: true, content: openDocument.getText() };
    }
    try {
      const bytes = await vscode.workspace.fs.readFile(uri);
      return { exists: true, content: new TextDecoder().decode(bytes) };
    } catch (error: unknown) {
      if (isFileNotFound(error)) {
        return { exists: false, content: "" };
      }
      throw error;
    }
  }

  private selectWorkspaceFolder(requestedPath: string): {
    folder: vscode.WorkspaceFolder;
    requestedPath: string;
  } {
    const folders = vscode.workspace.workspaceFolders;
    if (folders === undefined || folders.length === 0) {
      throw new Error("Open a workspace before applying SC-EVM edits");
    }
    const normalized = requestedPath.replaceAll("\\", "/");
    if (folders.length === 1) {
      const folder = folders[0]!;
      const prefix = `${folder.name}/`;
      return {
        folder,
        requestedPath: normalized.startsWith(prefix)
          ? normalized.slice(prefix.length)
          : normalized,
      };
    }
    for (const folder of folders) {
      const prefix = `${folder.name}/`;
      if (normalized.startsWith(prefix)) {
        return { folder, requestedPath: normalized.slice(prefix.length) };
      }
    }
    throw new Error(
      "Multi-root workspace edit must start with an authoritative workspace folder name",
    );
  }
}

function isFileNotFound(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "FileNotFound";
}
