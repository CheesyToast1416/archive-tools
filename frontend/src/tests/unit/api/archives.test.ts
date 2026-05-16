import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("$lib/api/client", () => ({
  apiPost: vi.fn().mockResolvedValue({ ok: true }),
  ssePost: vi.fn().mockResolvedValue(undefined),
  mediaUrl: vi.fn().mockResolvedValue("http://127.0.0.1:19999/preview/serve?path=x&token=t"),
}));

import { apiPost, ssePost, mediaUrl } from "$lib/api/client";
import {
  listArchive,
  getArchiveInfo,
  detectEncoding,
  testArchive,
  extractArchive,
  batchExtract,
  createArchive,
  convertArchive,
  updateArchive,
  extractPreview,
  cleanupPreview,
  getPreviewServeUrl,
} from "$lib/api/archives";

const post = vi.mocked(apiPost);
const sse = vi.mocked(ssePost);
const media = vi.mocked(mediaUrl);

beforeEach(() => {
  post.mockResolvedValue({ ok: true });
  sse.mockResolvedValue(undefined);
});

describe("listArchive", () => {
  it("POSTs to /archives/list", async () => {
    post.mockResolvedValue({ ok: true, encoding: null, names: ["a.txt"] });
    const r = await listArchive({ archive_path: "/a.zip" });
    expect(post).toHaveBeenCalledWith("/archives/list", { archive_path: "/a.zip" });
    expect(r.names).toEqual(["a.txt"]);
  });
});

describe("getArchiveInfo", () => {
  it("POSTs to /archives/info", async () => {
    await getArchiveInfo({ archive_path: "/a.zip", password: "pw" });
    expect(post).toHaveBeenCalledWith("/archives/info", { archive_path: "/a.zip", password: "pw" });
  });
});

describe("detectEncoding", () => {
  it("POSTs to /archives/detect-encoding", async () => {
    await detectEncoding({ archive_path: "/a.zip" });
    expect(post).toHaveBeenCalledWith("/archives/detect-encoding", { archive_path: "/a.zip" });
  });
});

describe("testArchive", () => {
  it("POSTs to /archives/test", async () => {
    await testArchive({ archive_path: "/a.zip" });
    expect(post).toHaveBeenCalledWith("/archives/test", { archive_path: "/a.zip" });
  });
});

describe("extractArchive", () => {
  it("calls ssePost with /archives/extract", async () => {
    const handlers = { complete: vi.fn() };
    await extractArchive({ archive_path: "/a.zip" }, handlers);
    expect(sse).toHaveBeenCalledWith("/archives/extract", { archive_path: "/a.zip" }, handlers);
  });
});

describe("batchExtract", () => {
  it("calls ssePost with /archives/batch", async () => {
    const handlers = { complete: vi.fn() };
    await batchExtract({ archives: ["/a.zip", "/b.zip"] }, handlers);
    expect(sse).toHaveBeenCalledWith(
      "/archives/batch",
      { archives: ["/a.zip", "/b.zip"] },
      handlers
    );
  });
});

describe("createArchive", () => {
  it("POSTs to /archives/create", async () => {
    await createArchive({ output_path: "/out.zip", files: ["/a.txt"], format: "zip" });
    expect(post).toHaveBeenCalledWith(
      "/archives/create",
      expect.objectContaining({ format: "zip" })
    );
  });
});

describe("convertArchive", () => {
  it("POSTs to /archives/convert", async () => {
    await convertArchive({ input_path: "/a.zip", output_path: "/b.7z", output_format: "7z" });
    expect(post).toHaveBeenCalledWith(
      "/archives/convert",
      expect.objectContaining({ output_format: "7z" })
    );
  });
});

describe("updateArchive", () => {
  it("POSTs to /archives/update", async () => {
    await updateArchive({ archive_path: "/a.zip", files_to_add: ["/x.txt"] });
    expect(post).toHaveBeenCalledWith(
      "/archives/update",
      expect.objectContaining({ archive_path: "/a.zip" })
    );
  });
});

describe("extractPreview", () => {
  it("POSTs to /preview/", async () => {
    post.mockResolvedValue({ temp_id: "abc", file_path: "/tmp/abc/img.png" });
    const r = await extractPreview({ archive_path: "/a.zip", entry_name: "img.png" });
    expect(post).toHaveBeenCalledWith(
      "/preview/",
      expect.objectContaining({ entry_name: "img.png" })
    );
    expect(r.temp_id).toBe("abc");
  });
});

describe("cleanupPreview", () => {
  it("POSTs to /preview/:id", async () => {
    await cleanupPreview("abc123");
    expect(post).toHaveBeenCalledWith("/preview/abc123", {});
  });
});

describe("getPreviewServeUrl", () => {
  it("calls mediaUrl with /preview/serve", async () => {
    const url = await getPreviewServeUrl("/tmp/file.png");
    expect(media).toHaveBeenCalledWith("/preview/serve", "/tmp/file.png");
    expect(url).toContain("preview");
  });
});
