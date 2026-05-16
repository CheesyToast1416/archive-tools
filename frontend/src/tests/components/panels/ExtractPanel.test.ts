import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("@tauri-apps/api/webviewWindow", () => ({
  getCurrentWebviewWindow: () => ({ onDragDropEvent: vi.fn().mockResolvedValue(() => {}) }),
}));
vi.mock("@tauri-apps/api/core", () => ({
  convertFileSrc: vi.fn((p: string) => `asset://${p}`),
}));
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue("/chosen/archive.zip"),
}));
vi.mock("@tauri-apps/plugin-notification", () => ({
  sendNotification: vi.fn(),
}));

vi.mock("$lib/api/archives", () => ({
  listArchive: vi
    .fn()
    .mockResolvedValue({ ok: true, encoding: null, names: ["readme.txt", "photo.jpg", "src/"] }),
  getArchiveInfo: vi.fn().mockResolvedValue({
    format_name: "ZIP",
    file_count: 3,
    compressed_size: 1024,
    uncompressed_size: 4096,
    is_encrypted: false,
    comment: "",
  }),
  detectEncoding: vi.fn().mockResolvedValue({ encoding: null, confidence: 0 }),
  testArchive: vi.fn().mockResolvedValue({ ok: true, failed: [] }),
  extractArchive: vi.fn().mockImplementation((_p, handlers) => {
    handlers.progress?.({ current: 1, total: 2 });
    handlers.complete?.({ ok: true });
    return Promise.resolve();
  }),
  extractPreview: vi.fn().mockResolvedValue({ temp_id: "t1", file_path: "/tmp/readme.txt" }),
  cleanupPreview: vi.fn().mockResolvedValue({ ok: true }),
  getPreviewServeUrl: vi
    .fn()
    .mockResolvedValue("http://127.0.0.1:19999/preview/serve?path=/tmp/readme.txt&token=t"),
  updateArchive: vi.fn().mockResolvedValue({ ok: true }),
}));

vi.mock("$lib/stores/uiState", () => ({
  addRecent: vi.fn().mockResolvedValue(undefined),
}));

const { pendingPathStore, appSettingsStore } = vi.hoisted(() => {
  const pendingPathStore = {
    subscribe: vi.fn((fn: (v: unknown) => void) => {
      fn(null);
      return () => {};
    }),
    set: vi.fn(),
  };
  const appSettingsStore = {
    subscribe: vi.fn((fn: (v: object) => void) => {
      fn({
        smart_extraction: true,
        trash_after_extract: false,
        default_output_dir: "",
        trash_after_create: false,
        trash_after_batch: false,
        default_password_encoding: "",
        default_filename_encoding: "",
        notifications_enabled: true,
      });
      return () => {};
    }),
  };
  return { pendingPathStore, appSettingsStore };
});

vi.mock("$lib/stores/archive", () => ({ pendingArchivePath: pendingPathStore }));
vi.mock("$lib/stores/appSettings", () => ({ appSettings: appSettingsStore }));
vi.mock("$lib/api/passwords", () => ({
  listPasswords: vi.fn().mockResolvedValue([]),
  getPasswordSecret: vi.fn().mockResolvedValue({ password: "" }),
}));

import { listArchive, testArchive, extractArchive } from "$lib/api/archives";
import ExtractPanel from "$lib/components/panels/ExtractPanel.svelte";

const mockList = vi.mocked(listArchive);
const mockTest = vi.mocked(testArchive);
const mockExtract = vi.mocked(extractArchive);

async function openArchive(container: HTMLElement, getByText: (text: string) => HTMLElement) {
  // Simulate dropping a file via pendingArchivePath subscription
  // Instead, click browse button in the drop zone
  await fireEvent.click(getByText("Browse Files"));
  await waitFor(() => expect(mockList).toHaveBeenCalled());
}

beforeEach(() => vi.clearAllMocks());

describe("ExtractPanel", () => {
  it("shows FileDropZone initially", () => {
    const { getByText } = render(ExtractPanel);
    expect(getByText("Drop an archive here")).toBeInTheDocument();
  });

  it("opening an archive calls listArchive", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({ archive_path: "/chosen/archive.zip" })
    );
  });

  it("shows archive entries after listing", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => expect(getByText("readme.txt")).toBeInTheDocument());
  });

  it("shows archive name in header bar", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => expect(getByText("archive.zip")).toBeInTheDocument());
  });

  it("shows Test button after archive is opened", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => expect(getByText("Test")).toBeInTheDocument());
  });

  it("Test button calls testArchive", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => getByText("Test"));
    await fireEvent.click(getByText("Test"));
    await waitFor(() => expect(mockTest).toHaveBeenCalled());
  });

  it("Test success shows OK message in log", async () => {
    const { getByText, findByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => getByText("Test"));
    await fireEvent.click(getByText("Test"));
    await waitFor(() => getByText("Log"));
    await fireEvent.click(getByText("Log"));
    expect(await findByText("✓ Archive integrity OK.")).toBeInTheDocument();
  });

  it("Extract button calls extractArchive", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => getByText("Extract"));
    await fireEvent.click(getByText("Extract"));
    await waitFor(() => expect(mockExtract).toHaveBeenCalled());
  });

  it("shows extraction complete message in log", async () => {
    const { getByText, findByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => getByText("Extract"));
    await fireEvent.click(getByText("Extract"));
    // Wait for the mock to have been called and log to appear
    await waitFor(() => expect(mockExtract).toHaveBeenCalled());
    await waitFor(() => getByText("Log"), { timeout: 3000 });
    await fireEvent.click(getByText("Log"));
    expect(await findByText(/Extraction complete/)).toBeInTheDocument();
  });

  it("close button returns to drop zone", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => getByText("archive.zip"));
    await fireEvent.click(document.querySelector(".close-btn")!);
    await waitFor(() => expect(getByText("Drop an archive here")).toBeInTheDocument());
  });

  it("shows password-protected dialog when listArchive returns ok: false", async () => {
    mockList.mockResolvedValueOnce({ ok: false, encoding: null, names: [] });
    const { getByText, findByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    expect(await findByText("Password Required")).toBeInTheDocument();
  });

  it("Edit button shows in archive view", async () => {
    const { getByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => expect(getByText("Edit")).toBeInTheDocument());
  });

  it("Encoding section toggles on click", async () => {
    const { getByText, queryByText } = render(ExtractPanel);
    await openArchive(document.body as HTMLElement, getByText);
    await waitFor(() => getByText("Encoding"));
    expect(queryByText("Filenames")).toBeNull();
    await fireEvent.click(getByText("Encoding"));
    expect(getByText("Filenames")).toBeInTheDocument();
  });
});
