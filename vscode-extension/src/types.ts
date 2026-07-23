export type SessionId = string & { readonly __brand: "SessionId" };

export type SaveFileAction = Readonly<{
  type: "save_file";
  payload: Readonly<{
    file_path: string;
    file_content: string;
  }>;
}>;

export type ReadFileAction = Readonly<{
  type: "read_file";
  payload: Readonly<{ file_path: string }>;
}>;

export type ListFilesAction = Readonly<{
  type: "list_files";
  payload: Readonly<{ glob?: string; max_results?: number }>;
}>;

export type UnsupportedAction = Readonly<{
  type: string;
  payload?: unknown;
}>;

export type EngineAction = SaveFileAction | ReadFileAction | ListFilesAction | UnsupportedAction;

export type StreamEvent =
  | Readonly<{ kind: "content"; content: string }>
  | Readonly<{ kind: "progress"; message: string }>
  | Readonly<{ kind: "usage"; model1: unknown; model2: unknown }>
  | Readonly<{ kind: "action"; action: EngineAction }>
  | Readonly<{ kind: "warning"; message: string }>;

export type ApprovedContext = Readonly<{
  path: string;
  content: string;
  source: "attachment" | "activeEditor" | "workspaceInventory" | "workspaceFile";
}>;

export type WorkspaceScope = Readonly<{
  folders: readonly string[];
  activeFile?: string;
}>;

export function createSessionId(uuid: string): SessionId {
  const normalized = `vscode_${uuid.replaceAll("-", "")}`;
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(normalized)) {
    throw new Error("Could not create a valid SC-EVM session identifier");
  }
  return normalized as SessionId;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseEngineAction(value: unknown): EngineAction | undefined {
  if (!isRecord(value) || typeof value.type !== "string" || value.type === "none") {
    return undefined;
  }
  if (value.type === "read_file") {
    if (!isRecord(value.payload) || typeof value.payload.file_path !== "string") {
      return { type: value.type };
    }
    return { type: "read_file", payload: { file_path: value.payload.file_path } };
  }
  if (value.type === "list_files") {
    if (!isRecord(value.payload)) {
      return { type: "list_files", payload: {} };
    }
    const glob = typeof value.payload.glob === "string" ? value.payload.glob : undefined;
    const maxResults =
      typeof value.payload.max_results === "number" ? value.payload.max_results : undefined;
    return {
      type: "list_files",
      payload: {
        ...(glob === undefined ? {} : { glob }),
        ...(maxResults === undefined ? {} : { max_results: maxResults }),
      },
    };
  }
  if (value.type !== "save_file") {
    return { type: value.type, payload: value.payload };
  }
  if (!isRecord(value.payload)) {
    return { type: value.type };
  }
  const filePath = value.payload.file_path;
  const fileContent = value.payload.file_content;
  if (typeof filePath !== "string" || typeof fileContent !== "string") {
    return { type: value.type };
  }
  return {
    type: "save_file",
    payload: { file_path: filePath, file_content: fileContent },
  };
}

export function isSaveFileAction(action: EngineAction): action is SaveFileAction {
  return action.type === "save_file" && "payload" in action && action.payload !== undefined;
}

export function isReadFileAction(action: EngineAction): action is ReadFileAction {
  return action.type === "read_file" && "payload" in action && action.payload !== undefined;
}

export function isListFilesAction(action: EngineAction): action is ListFilesAction {
  return action.type === "list_files" && "payload" in action && action.payload !== undefined;
}
