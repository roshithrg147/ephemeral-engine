import { Buffer } from "node:buffer";
import * as path from "node:path";
import * as vscode from "vscode";

import {
  isBlockedWorkspacePath,
  redactSecretLines,
  resolveWorkspacePath,
} from "./security.js";
import type {
  ApprovedContext,
  ListFilesAction,
  ReadFileAction,
  WorkspaceScope,
} from "./types.js";

const SEARCH_EXCLUDE =
  "**/{.git,.next,.venv,__pycache__,build,coverage,dist,node_modules,out,target,venv}/**";
const MAX_INVENTORY_FILES = 2000;
const MAX_SINGLE_FILE_BYTES = 64 * 1024;
const MAX_SEED_FILE_BYTES = 12 * 1024;

const HIGH_SIGNAL_NAMES = new Set([
  "agents.md",
  "architecture.md",
  "cargo.toml",
  "compose.yaml",
  "docker-compose.yml",
  "dockerfile",
  "go.mod",
  "package.json",
  "pom.xml",
  "pyproject.toml",
  "readme.md",
  "requirements.txt",
  "tsconfig.json",
  "vite.config.js",
  "vite.config.ts",
]);

export type WorkspaceToolResult = Readonly<{
  label: string;
  content: string;
}>;

export class WorkspaceToolService {
  public async buildReviewContexts(
    scope: WorkspaceScope,
    maxBytes: number,
  ): Promise<ApprovedContext[]> {
    const paths = await this.listSafePaths("**/*", MAX_INVENTORY_FILES);
    const inventoryBudget = Math.min(Math.floor(maxBytes * 0.4), 24 * 1024);
    const inventory = this.boundText(
      [
        `Workspace folders: ${scope.folders.join(", ")}`,
        `Active file: ${scope.activeFile ?? "none"}`,
        `Safe files discovered: ${paths.length}`,
        ...paths,
      ].join("\n"),
      inventoryBudget,
    );
    const contexts: ApprovedContext[] = [
      {
        path: "<workspace-inventory>",
        content: inventory,
        source: "workspaceInventory",
      },
    ];
    let remaining = maxBytes - Buffer.byteLength(inventory, "utf8");
    const prioritized = this.prioritizePaths(paths, scope.activeFile);
    for (const filePath of prioritized) {
      if (remaining <= 0) {
        break;
      }
      const context = await this.readSafeFile(filePath, Math.min(remaining, MAX_SEED_FILE_BYTES));
      if (context === undefined) {
        continue;
      }
      contexts.push(context);
      remaining -= Buffer.byteLength(context.content, "utf8");
    }
    return contexts;
  }

  public async executeRead(action: ReadFileAction): Promise<WorkspaceToolResult> {
    const context = await this.readSafeFile(action.payload.file_path, MAX_SINGLE_FILE_BYTES);
    if (context === undefined) {
      throw new Error(`Workspace file cannot be read safely: ${action.payload.file_path}`);
    }
    return { label: `read_file ${context.path}`, content: context.content };
  }

  public async executeList(action: ListFilesAction): Promise<WorkspaceToolResult> {
    const glob = action.payload.glob ?? "**/*";
    validateGlob(glob);
    const maxResults = Math.max(
      1,
      Math.min(MAX_INVENTORY_FILES, Math.trunc(action.payload.max_results ?? 500)),
    );
    const paths = await this.listSafePaths(glob, maxResults);
    return {
      label: `list_files ${glob}`,
      content: [`Safe files matched: ${paths.length}`, ...paths].join("\n"),
    };
  }

  private async listSafePaths(glob: string, maxResults: number): Promise<string[]> {
    const uris = await vscode.workspace.findFiles(
      this.resolveGlob(glob),
      SEARCH_EXCLUDE,
      maxResults,
    );
    const paths = uris
      .filter((uri) => uri.scheme === "file" && !isBlockedWorkspacePath(uri.fsPath))
      .map((uri) => this.displayPath(uri))
      .sort((left, right) => left.localeCompare(right));
    return [...new Set(paths)];
  }

  private prioritizePaths(paths: readonly string[], activeFile?: string): string[] {
    const highSignal = paths.filter((filePath) => {
      const basename = path.posix.basename(filePath).toLowerCase();
      return HIGH_SIGNAL_NAMES.has(basename) || basename.startsWith("readme.");
    });
    if (activeFile !== undefined && paths.includes(activeFile)) {
      highSignal.unshift(activeFile);
    }
    return [...new Set(highSignal)].slice(0, 12);
  }

  private async readSafeFile(
    scopedPath: string,
    maxBytes: number,
  ): Promise<ApprovedContext | undefined> {
    const { folder, requestedPath } = this.selectWorkspaceFolder(scopedPath);
    const resolved = await resolveWorkspacePath(folder.uri.fsPath, requestedPath);
    if (isBlockedWorkspacePath(resolved)) {
      return undefined;
    }
    const uri = vscode.Uri.file(resolved);
    const stat = await vscode.workspace.fs.stat(uri);
    if (stat.type !== vscode.FileType.File || stat.size > MAX_SINGLE_FILE_BYTES) {
      return undefined;
    }
    const bytes = await vscode.workspace.fs.readFile(uri);
    if (bytes.includes(0)) {
      return undefined;
    }
    const content = redactSecretLines(new TextDecoder().decode(bytes));
    return {
      path: this.displayPath(uri),
      content: this.boundText(content, maxBytes),
      source: "workspaceFile",
    };
  }

  private selectWorkspaceFolder(scopedPath: string): {
    folder: vscode.WorkspaceFolder;
    requestedPath: string;
  } {
    const folders = vscode.workspace.workspaceFolders;
    if (folders === undefined || folders.length === 0) {
      throw new Error("Open a workspace before using SC-EVM workspace tools");
    }
    const normalized = scopedPath.replaceAll("\\", "/");
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
    throw new Error("Multi-root workspace path must start with a workspace folder name");
  }

  private resolveGlob(glob: string): vscode.GlobPattern {
    const folders = vscode.workspace.workspaceFolders;
    if (folders === undefined || folders.length === 0) {
      throw new Error("Open a workspace before using SC-EVM workspace tools");
    }
    const normalized = glob.replaceAll("\\", "/");
    for (const folder of folders) {
      const prefix = `${folder.name}/`;
      if (normalized.startsWith(prefix)) {
        return new vscode.RelativePattern(folder, normalized.slice(prefix.length));
      }
    }
    return normalized;
  }

  private displayPath(uri: vscode.Uri): string {
    const folder = vscode.workspace.getWorkspaceFolder(uri);
    if (folder === undefined) {
      throw new Error("Workspace tool result escaped the open workspace");
    }
    const relative = path.relative(folder.uri.fsPath, uri.fsPath).split(path.sep).join("/");
    return (vscode.workspace.workspaceFolders?.length ?? 0) > 1
      ? `${folder.name}/${relative}`
      : relative;
  }

  private boundText(value: string, maxBytes: number): string {
    return Buffer.from(value, "utf8").subarray(0, maxBytes).toString("utf8");
  }
}

function validateGlob(glob: string): void {
  if (
    glob.length === 0 ||
    glob.length > 200 ||
    glob.includes("..") ||
    path.isAbsolute(glob) ||
    !/^[A-Za-z0-9_./*?[\]{}!@()+,\-]+$/.test(glob)
  ) {
    throw new Error("Invalid workspace file glob");
  }
}
