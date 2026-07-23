export type SseEvent = Readonly<{
  event: string;
  data: string;
}>;

export class SseDecoder {
  private event = "message";
  private readonly dataLines: string[] = [];

  public feedLine(line: string): SseEvent[] {
    if (line === "") {
      return this.dispatch();
    }
    if (line.startsWith(":")) {
      return [];
    }

    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    let value = separator === -1 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    if (field === "event") {
      this.event = value || "message";
    } else if (field === "data") {
      this.dataLines.push(value);
    }
    return [];
  }

  public finish(): SseEvent[] {
    return this.dispatch();
  }

  private dispatch(): SseEvent[] {
    if (this.dataLines.length === 0) {
      this.event = "message";
      return [];
    }
    const result = [{ event: this.event, data: this.dataLines.join("\n") }] satisfies SseEvent[];
    this.event = "message";
    this.dataLines.length = 0;
    return result;
  }
}

export function decodeSseData(data: string): unknown {
  if (data === "[DONE]") {
    return data;
  }
  try {
    return JSON.parse(data) as unknown;
  } catch {
    return data;
  }
}

export async function* decodeSseStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = stream.getReader();
  const textDecoder = new TextDecoder();
  const decoder = new SseDecoder();
  let buffer = "";
  try {
    while (true) {
      const result = await reader.read();
      if (result.done) {
        break;
      }
      buffer += textDecoder.decode(result.value, { stream: true }).replace(/\r\n/g, "\n");
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + 1);
        for (const event of decoder.feedLine(line)) {
          yield event;
        }
        newline = buffer.indexOf("\n");
      }
    }
    buffer += textDecoder.decode();
    if (buffer.length > 0) {
      for (const event of decoder.feedLine(buffer)) {
        yield event;
      }
    }
    for (const event of decoder.finish()) {
      yield event;
    }
  } finally {
    reader.releaseLock();
  }
}
