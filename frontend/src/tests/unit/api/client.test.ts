import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { apiDelete, apiGet, apiPost, apiPut, mediaUrl, ssePost } from "$lib/api/client";

// Mock @tauri-apps/api/core so invoke resolves immediately with a connection
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn().mockResolvedValue({ port: 19999, token: "tok" }),
  convertFileSrc: vi.fn((p: string) => `asset://${p}`),
}));

const mockInvoke = vi.mocked(invoke);

function makeResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  // Ensure Tauri bridge is "ready"
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
  mockInvoke.mockResolvedValue({ port: 19999, token: "tok" });
});

afterEach(() => vi.restoreAllMocks());

describe("apiGet", () => {
  it("fetches from correct URL with auth header", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(makeResponse({ value: 1 }));
    const result = await apiGet<{ value: number }>("/test");
    expect(spy).toHaveBeenCalledWith(
      "http://127.0.0.1:19999/test",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer tok" }) })
    );
    expect(result).toEqual({ value: 1 });
  });

  it("throws on HTTP error", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("Not Found", { status: 404 }));
    await expect(apiGet("/missing")).rejects.toThrow("HTTP 404");
  });
});

describe("apiPost", () => {
  it("sends JSON body with POST method", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(makeResponse({ ok: true }));
    await apiPost("/archives/list", { archive_path: "/a.zip" });
    const [, opts] = spy.mock.calls[0];
    expect(opts?.method).toBe("POST");
    expect(JSON.parse(opts?.body as string)).toEqual({ archive_path: "/a.zip" });
  });
});

describe("apiPut", () => {
  it("uses PUT method", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(makeResponse({ ok: true }));
    await apiPut("/settings/app", { smart_extraction: false });
    expect(spy.mock.calls[0][1]?.method).toBe("PUT");
  });
});

describe("apiDelete", () => {
  it("uses DELETE method and resolves void", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiDelete("/passwords/123")).resolves.toBeUndefined();
  });
});

describe("mediaUrl", () => {
  it("encodes path and appends token as query params", async () => {
    const url = await mediaUrl("/preview/serve", "/home/user/file with spaces.txt");
    expect(url).toContain("tok");
    expect(url).toContain(encodeURIComponent("/home/user/file with spaces.txt"));
    expect(url).toContain("/preview/serve");
  });
});

describe("ssePost", () => {
  function makeSSEStream(events: Array<{ event: string; data: unknown }>) {
    const text = events
      .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
      .join("");
    const stream = new ReadableStream({
      start(c) {
        c.enqueue(new TextEncoder().encode(text));
        c.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  }

  it("dispatches named events to handlers", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      makeSSEStream([
        { event: "progress", data: { current: 1, total: 10 } },
        { event: "complete", data: { ok: true } },
      ])
    );
    const progressHandler = vi.fn();
    const completeHandler = vi.fn();
    await ssePost(
      "/archives/extract",
      {},
      { progress: progressHandler, complete: completeHandler }
    );
    expect(progressHandler).toHaveBeenCalledWith({ current: 1, total: 10 });
    expect(completeHandler).toHaveBeenCalledWith({ ok: true });
  });

  it("ignores events with no registered handler", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(makeSSEStream([{ event: "unknown", data: {} }]));
    await expect(ssePost("/x", {}, {})).resolves.toBeUndefined();
  });

  it("throws on non-ok HTTP status", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("Error", { status: 500 }));
    await expect(ssePost("/x", {}, {})).rejects.toThrow("SSE /x → HTTP 500");
  });

  it("calls multiple handlers independently", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      makeSSEStream([
        { event: "log", data: { message: "line1" } },
        { event: "log", data: { message: "line2" } },
      ])
    );
    const logHandler = vi.fn();
    await ssePost("/x", {}, { log: logHandler });
    expect(logHandler).toHaveBeenCalledTimes(2);
    expect(logHandler).toHaveBeenNthCalledWith(1, { message: "line1" });
    expect(logHandler).toHaveBeenNthCalledWith(2, { message: "line2" });
  });
});
