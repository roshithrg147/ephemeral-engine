import type * as vscode from "vscode";

import { decodeSseData, decodeSseStream } from "./sse.js";
import {
  createSessionId,
  isRecord,
  parseEngineAction,
  type SessionId,
  type StreamEvent,
} from "./types.js";

type CancellationLike = Pick<vscode.CancellationToken, "isCancellationRequested" | "onCancellationRequested">;

export type ClientOptions = Readonly<{
  gateway: URL;
  timeoutSeconds: number;
  graphifyEnabled: boolean;
  developmentPhase: number;
  bearerToken?: string;
  onDiagnostic?: (event: string, detail?: string) => void;
  onAuthFailure?: () => Promise<string | null>;
}>;

export class ScevmClient {
  private sessionId: SessionId;
  private initialized = false;
  private initialization: Promise<void> | undefined;

  public constructor(private readonly options: ClientOptions) {
    this.sessionId = createSessionId(crypto.randomUUID());
  }

  public get activeSessionId(): SessionId {
    return this.sessionId;
  }

  public async health(): Promise<void> {
    this.diagnostic("health.start", this.options.gateway.origin);
    const response = await this.request("/", { method: "GET" });
    if (!response.ok) {
      throw new Error(`SC-EVM gateway health returned HTTP ${response.status}`);
    }
    this.diagnostic("health.ready", `HTTP ${response.status}`);
  }

  public async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }
    this.initialization ??= this.initializeOnce();
    try {
      await this.initialization;
    } finally {
      this.initialization = undefined;
    }
  }

  public async *query(prompt: string, cancellation: CancellationLike): AsyncGenerator<StreamEvent> {
    await this.initialize();
    this.diagnostic("query.start", `session=${this.sessionId}`);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.options.timeoutSeconds * 1000);
    const cancellationSubscription = cancellation.onCancellationRequested(() => controller.abort());
    const startedAt = performance.now();
    let eventCount = 0;
    let firstEventAt: number | undefined;
    try {
      if (cancellation.isCancellationRequested) {
        controller.abort();
      }
      const response = await this.request(
        "/api/agent/query",
        {
          method: "POST",
          headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: this.sessionId,
            prompt,
            graphify_enabled: this.options.graphifyEnabled,
            diagnostic_mode: false,
          }),
          signal: controller.signal,
        },
      );
      if (!response.ok) {
        throw await this.responseError("SC-EVM query failed", response);
      }
      if (!response.headers.get("content-type")?.includes("text/event-stream")) {
        throw new Error("SC-EVM query did not return an SSE stream");
      }
      if (response.body === null) {
        throw new Error("SC-EVM query returned an empty stream");
      }

      for await (const event of decodeSseStream(response.body)) {
        eventCount += 1;
        firstEventAt ??= performance.now();
        this.diagnostic("query.event", event.event ?? "message");
        const value = decodeSseData(event.data);
        if (event.event === "response_content" || event.event === "token") {
          const content = isRecord(value) ? value.content : value;
          if (typeof content === "string" && content.length > 0) {
            yield { kind: "content", content };
          }
        } else if (event.event === "query_reformulation" && isRecord(value)) {
          const intent = value.search_vector_query;
          if (typeof intent === "string") {
            yield { kind: "progress", message: `Intent aligned: ${intent}` };
          }
        } else if (event.event === "token_usage" && isRecord(value)) {
          yield { kind: "usage", model1: value.m1, model2: value.m2 };
        } else if (event.event === "degradation") {
          const reasons =
            isRecord(value) && Array.isArray(value.reasons)
              ? value.reasons.filter((reason): reason is string => typeof reason === "string")
              : [];
          const suffix = reasons.length === 0 ? "" : ` Reasons: ${reasons.join(", ")}.`;
          yield { kind: "warning", message: `SC-EVM returned a degraded model response.${suffix}` };
        } else if (event.event === "action") {
          const action = parseEngineAction(value);
          if (action !== undefined) {
            yield { kind: "action", action };
          }
        } else if (event.event === "error") {
          throw new Error(typeof value === "string" ? value : "SC-EVM stream failed");
        } else if (event.event === "done" || value === "[DONE]") {
          const ttft =
            firstEventAt === undefined ? "none" : `${Math.round(firstEventAt - startedAt)}ms`;
          this.diagnostic(
            "query.done",
            `events=${eventCount} ttft=${ttft} total=${Math.round(performance.now() - startedAt)}ms`,
          );
          return;
        }
      }
      throw new Error("SC-EVM SSE stream closed before the done event");
    } catch (error: unknown) {
      if (controller.signal.aborted) {
        this.diagnostic("query.cancelled");
        throw new Error("SC-EVM request was cancelled or timed out");
      }
      this.diagnostic("query.failed", error instanceof Error ? error.message : "unknown error");
      throw error;
    } finally {
      clearTimeout(timeout);
      cancellationSubscription.dispose();
    }
  }

  public async burn(): Promise<boolean> {
    if (!this.initialized) {
      return true;
    }
    const response = await this.request(`/api/session/burn/${this.sessionId}`, {
      method: "DELETE",
    });
    this.initialized = false;
    if (response.status !== 200 && response.status !== 404) {
      throw await this.responseError("SC-EVM burn failed", response);
    }
    const history = await this.request(`/api/session/history/${this.sessionId}`, { method: "GET" });
    return history.status === 404;
  }

  public async newSession(): Promise<void> {
    await this.burn();
    this.sessionId = createSessionId(crypto.randomUUID());
  }

  private async initializeOnce(): Promise<void> {
    this.diagnostic("session.initialize.start", `session=${this.sessionId}`);
    const response = await this.request("/api/session/initialize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: this.sessionId,
        development_phase: this.options.developmentPhase,
      }),
    });
    if (!response.ok) {
      throw await this.responseError("SC-EVM session initialization failed", response);
    }
    this.initialized = true;
    this.diagnostic("session.initialize.ready", `session=${this.sessionId}`);
  }

  private async request(path: string, init: RequestInit): Promise<Response> {
    const headers = new Headers(init.headers);
    if (this.options.bearerToken !== undefined && this.options.bearerToken.length > 0) {
      headers.set("Authorization", `Bearer ${this.options.bearerToken}`);
    }
    const signal = init.signal ?? AbortSignal.timeout(this.options.timeoutSeconds * 1000);
    const url = new URL(path, this.options.gateway);
    this.diagnostic("http.request", `${init.method ?? "GET"} ${url.pathname}`);
    try {
      const response = await fetch(url, { ...init, headers, signal });
      this.diagnostic("http.response", `${init.method ?? "GET"} ${url.pathname} ${response.status}`);

      // If unauthorized, allow caller to attempt an auth refresh flow and retry once.
      if (response.status === 401 && this.options.onAuthFailure) {
        try {
          const newToken = await this.options.onAuthFailure();
          if (newToken) {
            headers.set("Authorization", `Bearer ${newToken}`);
            const retry = await fetch(url, { ...init, headers, signal });
            this.diagnostic("http.response.retry", `${init.method ?? "GET"} ${url.pathname} ${retry.status}`);
            return retry;
          }
        } catch (err) {
          this.diagnostic("http.auth_refresh.failed", String(err));
        }
      }

      return response;
    } catch (error: unknown) {
      const reason = error instanceof Error ? error.message : "unknown network error";
      this.diagnostic("http.failed", `${init.method ?? "GET"} ${url.pathname}: ${reason}`);
      throw new Error(
        `Cannot reach SC-EVM gateway at ${this.options.gateway.origin}. Start the gateway and retry.`,
        { cause: error },
      );
    }
  }

  private async responseError(prefix: string, response: Response): Promise<Error> {
    let detail = "";
    try {
      const value = (await response.json()) as unknown;
      if (isRecord(value) && typeof value.detail === "string") {
        detail = `: ${value.detail.slice(0, 300)}`;
      }
    } catch {
      // The status code remains the safe error contract for non-JSON responses.
    }
    return new Error(`${prefix} (HTTP ${response.status})${detail}`);
  }

  private diagnostic(event: string, detail?: string): void {
    this.options.onDiagnostic?.(event, detail);
  }
}
