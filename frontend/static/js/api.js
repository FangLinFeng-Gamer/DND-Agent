import { apiBase } from "./state.js?v=20260620-isekai-events";

export async function api(path, options = {}) {
  const headers = {
    Accept: "application/json",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(`${apiBase}${path}`, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const error = new Error(readErrorMessage(payload) || `Request failed with ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export async function readStreamingResponse(adventureId, content, locale, onDelta, options = {}) {
  const response = await fetch(`${apiBase}/api/adventures/${adventureId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
    body: JSON.stringify({
      content,
      locale,
      ...(options.characterId ? { character_id: options.characterId } : {}),
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = new Error(readErrorMessage(payload) || `Request failed with ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  if (!response.body) {
    throw new Error("Streaming response is not available.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    lines.forEach((line) => {
      const event = parseStreamEvent(line);
      if (!event) {
        return;
      }
      if (event.type === "delta") {
        onDelta(event.content || "");
      }
      if (event.type === "final") {
        finalPayload = event;
      }
    });
  }

  const tail = parseStreamEvent(buffer);
  if (tail?.type === "final") {
    finalPayload = tail;
  }
  if (!finalPayload) {
    throw new Error("Streaming response ended without final payload.");
  }
  return finalPayload;
}

export async function resolvePendingCheck(adventureId, checkId, payload) {
  return api(`/api/adventures/${adventureId}/checks/${encodeURIComponent(checkId)}/resolve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function parseStreamEvent(line) {
  const trimmed = line.trim();
  return trimmed ? JSON.parse(trimmed) : null;
}

export function readErrorMessage(payload) {
  const detail = payload?.detail;
  const structured = detail?.error;
  if (structured?.message && structured?.code) {
    return `${structured.message} (${structured.code})`;
  }
  if (structured?.message) {
    return structured.message;
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => item.msg || item.message || item.type).filter(Boolean).join("; ");
  }
  if (typeof payload === "string") {
    return payload;
  }
  return "";
}
