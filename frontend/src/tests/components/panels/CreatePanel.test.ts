import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("@tauri-apps/api/webviewWindow", () => ({
  getCurrentWebviewWindow: () => ({ onDragDropEvent: vi.fn().mockResolvedValue(() => {}) }),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue(["/home/user/file.txt"]),
  save: vi.fn().mockResolvedValue("/home/user/output.zip"),
}));

vi.mock("$lib/api/archives", () => ({
  createArchive: vi.fn().mockResolvedValue({ ok: true }),
}));

const { appSettingsStore } = vi.hoisted(() => ({
  appSettingsStore: {
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
  },
}));

vi.mock("$lib/stores/appSettings", () => ({ appSettings: appSettingsStore }));
vi.mock("$lib/api/passwords", () => ({
  listPasswords: vi.fn().mockResolvedValue([]),
  getPasswordSecret: vi.fn().mockResolvedValue({ password: "" }),
}));

import { createArchive } from "$lib/api/archives";
import CreatePanel from "$lib/components/panels/CreatePanel.svelte";

const mockCreate = vi.mocked(createArchive);

beforeEach(() => vi.clearAllMocks());

describe("CreatePanel", () => {
  it("shows empty file list placeholder initially", () => {
    const { getByText } = render(CreatePanel);
    expect(getByText("Drag files here or use Add Files")).toBeInTheDocument();
  });

  it("Add Files button opens file dialog", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const { getByText } = render(CreatePanel);
    await fireEvent.click(getByText("Add Files"));
    expect(open).toHaveBeenCalled();
  });

  it("adds files from dialog to the list", async () => {
    const { getByText } = render(CreatePanel);
    await fireEvent.click(getByText("Add Files"));
    await waitFor(() => expect(getByText("file.txt")).toBeInTheDocument());
  });

  it("remove button removes file from list", async () => {
    const { getByText, queryByText } = render(CreatePanel);
    await fireEvent.click(getByText("Add Files"));
    await waitFor(() => getByText("file.txt"));
    await fireEvent.click(getByText("✕"));
    expect(queryByText("file.txt")).toBeNull();
  });

  it("Clear button removes all files", async () => {
    const { getByText, queryByText } = render(CreatePanel);
    await fireEvent.click(getByText("Add Files"));
    await waitFor(() => getByText("file.txt"));
    await fireEvent.click(getByText("Clear"));
    expect(queryByText("file.txt")).toBeNull();
  });

  it("default zip format shows no password field and has compression slider", () => {
    const { container } = render(CreatePanel);
    // zip format: no password, has compression
    expect(container.querySelector("input[placeholder='Archive password']")).toBeNull();
    expect(container.querySelector(".compression-row")).toBeInTheDocument();
  });

  it("format select renders all available formats", () => {
    const { container } = render(CreatePanel);
    const options = container.querySelectorAll("select option");
    const values = Array.from(options).map((o) => (o as HTMLOptionElement).value);
    expect(values).toContain("zip");
    expect(values).toContain("zip-aes");
    expect(values).toContain("7z");
    expect(values).toContain("tar");
  });

  it("Create Archive button is disabled when no output path or no files", () => {
    const { getByText } = render(CreatePanel);
    expect((getByText("Create Archive") as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows success log after successful creation", async () => {
    const { save } = await import("@tauri-apps/plugin-dialog");
    vi.mocked(save).mockResolvedValue("/out/archive.zip");
    const { getByText, findByText } = render(CreatePanel);
    await fireEvent.click(getByText("…"));
    await waitFor(() => {});
    await fireEvent.click(getByText("Add Files"));
    await waitFor(() => getByText("file.txt"));
    await fireEvent.click(getByText("Create Archive"));
    await waitFor(() => getByText("Log"), { timeout: 3000 });
    await fireEvent.click(getByText("Log"));
    expect(await findByText(/Archive created successfully/)).toBeInTheDocument();
  });

  it("shows failure log when creation fails", async () => {
    mockCreate.mockResolvedValue({ ok: false });
    const { save } = await import("@tauri-apps/plugin-dialog");
    vi.mocked(save).mockResolvedValue("/out/archive.zip");
    const { getByText, findByText } = render(CreatePanel);
    await fireEvent.click(getByText("…"));
    await waitFor(() => {});
    await fireEvent.click(getByText("Add Files"));
    await waitFor(() => getByText("file.txt"));
    await fireEvent.click(getByText("Create Archive"));
    // ✗ prefix in log auto-expands CollapsibleLog — no need to click "Log"
    expect(await findByText(/Archive creation failed/, {}, { timeout: 3000 })).toBeInTheDocument();
  });
});
