import type { PatientSummary } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchPatients(query: string): Promise<PatientSummary[]> {
  const url = new URL("/patients", API_BASE);
  if (query) url.searchParams.set("query", query);
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to fetch patients: ${response.status}`);
  }
  return response.json();
}

export interface HarnessVersions {
  versions: string[];
  default: string;
}

export async function fetchHarnessVersions(): Promise<HarnessVersions> {
  const response = await fetch(new URL("/harness-versions", API_BASE));
  if (!response.ok) {
    throw new Error(`Failed to fetch harness versions: ${response.status}`);
  }
  return response.json();
}

export type SSEEventHandler = (eventType: string, data: string) => void;

/**
 * POST `body` to `path` on the viewer API and stream back Server-Sent
 * Events, calling `onEvent` for each one as it arrives.
 *
 * The browser's built-in EventSource only supports GET, and every stream
 * here (an investigation, a chat turn, a cohort run) needs a POST body -
 * so this reads the fetch Response's body stream directly and parses the
 * `event:`/`data:` framing by hand. This is the one place that framing is
 * parsed; every caller just gets (eventType, jsonString) pairs.
 */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: SSEEventHandler,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(new URL(path, API_BASE), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream request to ${path} failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // A blank line separates SSE messages, but "blank" depends on which line
  // ending the server uses. sse_starlette (our backend) defaults to "\r\n"
  // for every line, so a message boundary is literally "\r\n\r\n" - matching
  // only "\n\n" here silently matched nothing, ever, and the browser's own
  // SSE-aware devtools view (which accepts either) made that look like a
  // false alarm. Match both so this doesn't depend on the backend's choice.
  const BOUNDARY = /\r\n\r\n|\n\n/;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let match = BOUNDARY.exec(buffer);
    while (match !== null) {
      parseSSEMessage(buffer.slice(0, match.index), onEvent);
      buffer = buffer.slice(match.index + match[0].length);
      match = BOUNDARY.exec(buffer);
    }
  }
}

function parseSSEMessage(raw: string, onEvent: SSEEventHandler): void {
  let eventType = "message";
  const dataLines: string[] = [];
  for (const line of raw.split(/\r\n|\n/)) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length > 0) {
    onEvent(eventType, dataLines.join("\n"));
  }
}
