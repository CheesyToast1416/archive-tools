import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ARCHIVE_EXTENSIONS,
  ARCHIVE_FORMATS,
  formatBytes,
  NAV_BATCH,
  NAV_CONVERT,
  NAV_CREATE,
  NAV_EXTRACT,
  NAV_RECENT,
  relativeTime,
} from "$lib/constants";

describe("formatBytes", () => {
  it("returns ? for negative values", () => expect(formatBytes(-1)).toBe("?"));
  it("returns 0 B", () => expect(formatBytes(0)).toBe("0 B"));
  it("returns bytes for values under 1 KB", () => expect(formatBytes(500)).toBe("500 B"));
  it("returns 1023 B", () => expect(formatBytes(1023)).toBe("1023 B"));
  it("formats KB", () => expect(formatBytes(1024)).toBe("1.0 KB"));
  it("formats KB with decimal", () => expect(formatBytes(1536)).toBe("1.5 KB"));
  it("formats MB", () => expect(formatBytes(1024 ** 2)).toBe("1.0 MB"));
  it("formats GB", () => expect(formatBytes(1024 ** 3)).toBe("1.0 GB"));
  it("formats TB", () => expect(formatBytes(1024 ** 4)).toBe("1.0 TB"));
  it("formats large TB value", () => expect(formatBytes(2.5 * 1024 ** 4)).toBe("2.5 TB"));
});

describe("relativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-06-15T12:00:00Z"));
  });

  afterEach(() => vi.useRealTimers());

  it("returns 'Just now' for under 1 minute", () => {
    const d = new Date(Date.now() - 30_000);
    expect(relativeTime(d)).toBe("Just now");
  });

  it("returns minutes ago", () => {
    const d = new Date(Date.now() - 45 * 60_000);
    expect(relativeTime(d)).toBe("45m ago");
  });

  it("returns hours ago", () => {
    const d = new Date(Date.now() - 3 * 60 * 60_000);
    expect(relativeTime(d)).toBe("3h ago");
  });

  it("returns 'Yesterday' for exactly 1 day", () => {
    const d = new Date(Date.now() - 25 * 60 * 60_000);
    expect(relativeTime(d)).toBe("Yesterday");
  });

  it("returns days ago", () => {
    const d = new Date(Date.now() - 5 * 24 * 60 * 60_000);
    expect(relativeTime(d)).toBe("5 days ago");
  });

  it("returns locale date for over a week", () => {
    const d = new Date(Date.now() - 10 * 24 * 60 * 60_000);
    expect(relativeTime(d)).toBe(d.toLocaleDateString());
  });
});

describe("constants", () => {
  it("NAV constants are 0-4", () => {
    expect(NAV_RECENT).toBe(0);
    expect(NAV_EXTRACT).toBe(1);
    expect(NAV_CREATE).toBe(2);
    expect(NAV_BATCH).toBe(3);
    expect(NAV_CONVERT).toBe(4);
  });

  it("ARCHIVE_FORMATS has expected entries", () => {
    expect(ARCHIVE_FORMATS.length).toBeGreaterThan(0);
    const keys = ARCHIVE_FORMATS.map((f) => f.key);
    expect(keys).toContain("zip");
    expect(keys).toContain("7z");
    expect(keys).toContain("tar.gz");
  });

  it("zip-aes supports password, zip does not", () => {
    const zip = ARCHIVE_FORMATS.find((f) => f.key === "zip")!;
    const aes = ARCHIVE_FORMATS.find((f) => f.key === "zip-aes")!;
    expect(zip.supportsPassword).toBe(false);
    expect(aes.supportsPassword).toBe(true);
  });

  it("ARCHIVE_EXTENSIONS includes common formats", () => {
    expect(ARCHIVE_EXTENSIONS).toContain("zip");
    expect(ARCHIVE_EXTENSIONS).toContain("rar");
    expect(ARCHIVE_EXTENSIONS).toContain("7z");
    expect(ARCHIVE_EXTENSIONS).toContain("tar");
  });
});
