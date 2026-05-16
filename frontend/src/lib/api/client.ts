import { invoke } from "@tauri-apps/api/core";

interface ConnectionInfo {
  port: number;
  token: string;
}

let _conn: ConnectionInfo | null = null;

/**
 * Poll until the Tauri IPC bridge is ready and the sidecar has written its
 * handshake line.  The server prints its port from inside uvicorn's lifespan
 * startup — i.e. only after the socket is bound and accepting connections —
 * so no secondary health-check ping is needed.
 */
async function getConn(): Promise<ConnectionInfo> {
  if (_conn) return _conn;
  for (let i = 0; i < 100; i++) {
    // Wait for Tauri's IPC bridge to be injected into the WebView.
    // On slow machines this can take a few frames after page load.
    if (!(window as any).__TAURI_INTERNALS__) {
      await new Promise((r) => setTimeout(r, 50));
      continue;
    }
    try {
      const info = await invoke<ConnectionInfo | null>("get_connection_info");
      if (info) {
        _conn = info;
        return _conn;
      }
    } catch {
      // invoke threw — bridge initialised but sidecar not ready yet
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("ArchiveTools server did not start within 10 seconds");
}

function baseUrl(conn: ConnectionInfo, path: string): string {
  return `http://127.0.0.1:${conn.port}${path}`;
}

function authHeader(conn: ConnectionInfo): Record<string, string> {
  return { Authorization: `Bearer ${conn.token}` };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/** Build a URL with the auth token embedded as a query param.
 *  Used for media elements (<video>, <audio>) that cannot set request headers. */
export async function mediaUrl(serverPath: string, filePath: string): Promise<string> {
  const conn = await getConn();
  return `${baseUrl(conn, serverPath)}?path=${encodeURIComponent(filePath)}&token=${conn.token}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const conn = await getConn();
  const res = await fetch(baseUrl(conn, path), { headers: authHeader(conn) });
  return handleResponse<T>(res);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const conn = await getConn();
  const res = await fetch(baseUrl(conn, path), {
    method: "POST",
    headers: { ...authHeader(conn), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const conn = await getConn();
  const res = await fetch(baseUrl(conn, path), {
    method: "PUT",
    headers: { ...authHeader(conn), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function apiDelete(path: string): Promise<void> {
  const conn = await getConn();
  await fetch(baseUrl(conn, path), {
    method: "DELETE",
    headers: authHeader(conn),
  });
}

// ── SSE helper ────────────────────────────────────────────────────────────────

type SSEHandlers = Record<string, (data: unknown) => void>;

/**
 * POST `body` to `path`, read the response as a text/event-stream,
 * and dispatch named events to `handlers[eventName](parsedJSON)`.
 */
export async function ssePost(path: string, body: unknown, handlers: SSEHandlers): Promise<void> {
  const conn = await getConn();
  const res = await fetch(baseUrl(conn, path), {
    method: "POST",
    headers: { ...authHeader(conn), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`SSE ${path} → HTTP ${res.status}: ${text}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  const dataLines: string[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop()!;

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      } else if (line === "") {
        if (dataLines.length) {
          const raw = dataLines.join("\n");
          const handler = handlers[eventName];
          if (handler) {
            try {
              handler(JSON.parse(raw));
            } catch {
              handler(raw);
            }
          }
          eventName = "message";
          dataLines.length = 0;
        }
      }
    }
  }
}
