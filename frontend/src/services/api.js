const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "/api/v1"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    message,
    { status = 500, code = "API_ERROR", requestId = "unknown", details = null } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

function toNetworkApiError(err) {
  if (err instanceof ApiError) return err;
  return new ApiError(
    "Unable to connect to the FintechDemo backend API. Confirm the FastAPI server is running.",
    {
      status: 0,
      code: "NETWORK_ERROR",
      requestId: null,
      details: { retryable: true, reason: err?.message || "NetworkError" },
    },
  );
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });
  } catch (err) {
    throw toNetworkApiError(err);
  }

  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const err = payload?.error;
    throw new ApiError(err?.message || `Request failed (${response.status})`, {
      status: response.status,
      code: err?.code || "HTTP_ERROR",
      requestId: err?.request_id || response.headers.get("X-Request-ID") || "unknown",
      details: err?.details ?? null,
    });
  }

  return payload;
}

export function fetchHealth() {
  return requestJson("/health");
}

export function fetchDocuments() {
  return requestJson("/documents");
}

export function fetchDocumentChunks(sourceId) {
  return requestJson(`/documents/${encodeURIComponent(sourceId)}/chunks`);
}

export function ingestDocument(payload) {
  return requestJson("/documents/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function seedInitialDocuments() {
  return requestJson("/documents/seed", {
    method: "POST",
  });
}

export function fetchAuditLogs(limit = 25) {
  return requestJson(`/copilot/audit?limit=${limit}`);
}

/**
 * Stream LangGraph stages and final verified result (or structured SSE error) over fetch.
 */
export async function streamCopilotQuery(
  payload,
  { onStage, onResult, signal } = {},
) {
  let response;
  try {
    response = await fetch(`${API_BASE}/copilot/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    throw toNetworkApiError(err);
  }

  if (!response.ok) {
    const text = await response.text();
    let parsed = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }
    const err = parsed?.error;
    throw new ApiError(err?.message || `Stream request failed (${response.status})`, {
      status: response.status,
      code: err?.code || "STREAM_ERROR",
      requestId: err?.request_id || response.headers.get("X-Request-ID") || "unknown",
      details: err?.details ?? null,
    });
  }

  if (!response.body) {
    throw new ApiError("Streaming response body is unavailable.", { code: "STREAM_ERROR" });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult = null;
  let streamError = null;

  const processBlock = (block) => {
    const lines = block.split("\n");
    let eventName = "message";
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length === 0) return;

    const data = JSON.parse(dataLines.join("\n"));
    if (eventName === "stage" && onStage) {
      onStage(data.stage);
    } else if (eventName === "result") {
      finalResult = data;
      if (onResult) onResult(data);
    } else if (eventName === "error") {
      const err = data?.error || data;
      streamError = new ApiError(err?.message || "Copilot execution failed.", {
        status: response.status,
        code: err?.code || "STREAM_ERROR",
        requestId: err?.request_id || response.headers.get("X-Request-ID") || "unknown",
        details: err?.details ?? null,
      });
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);
      if (block) processBlock(block);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) {
    processBlock(buffer.trim());
  }

  if (streamError) {
    throw streamError;
  }

  return finalResult;
}
