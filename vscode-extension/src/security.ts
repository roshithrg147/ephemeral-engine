import * as fs from "node:fs/promises";
import * as path from "node:path";

export type WorkspacePath = string & { readonly __brand: "WorkspacePath" };

const BLOCKED_BASENAMES = new Set([
  ".env",
  ".npmrc",
  ".pypirc",
  "credentials",
  "credentials.json",
  "id_rsa",
  "id_ed25519",
]);
const BLOCKED_EXTENSIONS = new Set([".key", ".pem", ".p12", ".pfx"]);
const BLOCKED_SEGMENTS = new Set([
  ".git",
  ".next",
  ".venv",
  "__pycache__",
  "build",
  "coverage",
  "dist",
  "node_modules",
  "out",
  "target",
  "venv",
]);
const SECRET_LINE = /(?:api[_-]?key|access[_-]?token|bearer|client[_-]?secret|password|private[_-]?key)\s*[:=]/i;

export function validateGatewayUrl(raw: string, allowRemote: boolean): URL {
  const url = new URL(raw);
  if (!new Set(["http:", "https:"]).has(url.protocol)) {
    throw new Error("SC-EVM gateway must use HTTP or HTTPS");
  }
  const loopback = new Set(["127.0.0.1", "localhost", "::1"]).has(url.hostname);
  if (!loopback && !allowRemote) {
    throw new Error("Remote SC-EVM gateway is disabled in settings");
  }
  if (!loopback && url.protocol !== "https:") {
    throw new Error("Remote SC-EVM gateway must use HTTPS");
  }
  return url;
}

export function isBlockedContextPath(filePath: string): boolean {
  const basename = path.basename(filePath).toLowerCase();
  return (
    basename === ".env" ||
    basename.startsWith(".env.") ||
    BLOCKED_BASENAMES.has(basename) ||
    BLOCKED_EXTENSIONS.has(path.extname(basename))
  );
}

export function isBlockedWorkspacePath(filePath: string): boolean {
  const segments = filePath
    .split(/[\\/]+/)
    .filter(Boolean)
    .map((segment) => segment.toLowerCase());
  return segments.some((segment) => BLOCKED_SEGMENTS.has(segment)) || isBlockedContextPath(filePath);
}

export function redactSecretLines(content: string): string {
  return content
    .split(/\r?\n/)
    .map((line) => (SECRET_LINE.test(line) ? "[REDACTED SECRET-LIKE LINE]" : line))
    .join("\n");
}

export async function resolveWorkspacePath(
  workspaceRoot: string,
  requestedPath: string,
): Promise<WorkspacePath> {
  const realRoot = await fs.realpath(workspaceRoot);
  const candidate = path.resolve(realRoot, requestedPath);
  const relative = path.relative(realRoot, candidate);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("Proposed edit escapes the workspace");
  }

  let current = realRoot;
  for (const segment of relative.split(path.sep).filter(Boolean)) {
    current = path.join(current, segment);
    try {
      const stat = await fs.lstat(current);
      if (stat.isSymbolicLink()) {
        throw new Error("Proposed edit traverses a symbolic link");
      }
    } catch (error: unknown) {
      if (isNodeError(error) && error.code === "ENOENT") {
        break;
      }
      throw error;
    }
  }
  return candidate as WorkspacePath;
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && "code" in error;
}
