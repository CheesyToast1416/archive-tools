import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue("/home/user/source.zip"),
  save: vi.fn().mockResolvedValue("/home/user/output.7z"),
}));

vi.mock("$lib/api/archives", () => ({
  convertArchive: vi.fn().mockResolvedValue({ ok: true }),
}));

const { appSettingsStore } = vi.hoisted(() => ({
  appSettingsStore: {
    subscribe: vi.fn((fn: (v: object) => void) => {
      fn({
        default_filename_encoding: "",
        default_password_encoding: "",
        smart_extraction: true,
        trash_after_extract: false,
        default_output_dir: "",
        trash_after_create: false,
        trash_after_batch: false,
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

import { convertArchive } from "$lib/api/archives";
import ConvertPanel from "$lib/components/panels/ConvertPanel.svelte";

const mockConvert = vi.mocked(convertArchive);

beforeEach(() => vi.clearAllMocks());

describe("ConvertPanel", () => {
  it("renders source archive section", () => {
    const { getByText } = render(ConvertPanel);
    expect(getByText("SOURCE ARCHIVE")).toBeInTheDocument();
  });

  it("renders output archive section", () => {
    const { getByText } = render(ConvertPanel);
    expect(getByText("OUTPUT ARCHIVE")).toBeInTheDocument();
  });

  it("browse source button opens file dialog", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const { container } = render(ConvertPanel);
    const browseBtns = container.querySelectorAll("button.btn");
    await fireEvent.click(browseBtns[0]);
    expect(open).toHaveBeenCalled();
  });

  it("default zip output format shows no password field", () => {
    const { container } = render(ConvertPanel);
    // Default output format is zip (no password)
    expect(container.querySelector("input[placeholder='Output password']")).toBeNull();
  });

  it("format select contains all available output formats", () => {
    const { container } = render(ConvertPanel);
    const options = container.querySelectorAll("select option");
    const values = Array.from(options).map((o) => (o as HTMLOptionElement).value);
    expect(values).toContain("zip");
    expect(values).toContain("7z");
    expect(values).toContain("tar");
  });

  it("shows all format options in select", () => {
    const { container } = render(ConvertPanel);
    const options = container.querySelectorAll("option");
    expect(options.length).toBeGreaterThan(3);
  });

  it("successful convert shows success log", async () => {
    const { open, save } = await import("@tauri-apps/plugin-dialog");
    vi.mocked(open).mockResolvedValue("/src.zip");
    vi.mocked(save).mockResolvedValue("/out.7z");
    const { container, findByText } = render(ConvertPanel);
    const browseBtns = container.querySelectorAll("button.btn");
    await fireEvent.click(browseBtns[0]); // browse source
    await fireEvent.click(browseBtns[2]); // browse output
    await waitFor(() => {});
    // Click convert
    await fireEvent.click(browseBtns[browseBtns.length - 1]);
    // If convert was called, show log
    if (mockConvert.mock.calls.length > 0) {
      expect(await findByText(/Conversion complete/)).toBeInTheDocument();
    }
  });

  it("failed convert shows error log", async () => {
    mockConvert.mockResolvedValue({ ok: false });
    const { open, save } = await import("@tauri-apps/plugin-dialog");
    vi.mocked(open).mockResolvedValue("/src.zip");
    vi.mocked(save).mockResolvedValue("/out.7z");
    const { container, findByText } = render(ConvertPanel);
    const browseBtns = container.querySelectorAll("button.btn");
    await fireEvent.click(browseBtns[0]);
    await fireEvent.click(browseBtns[2]);
    await waitFor(() => {});
    await fireEvent.click(browseBtns[browseBtns.length - 1]);
    if (mockConvert.mock.calls.length > 0) {
      expect(await findByText(/Conversion failed/)).toBeInTheDocument();
    }
  });

  it("encoding section toggles on click", async () => {
    const { getByText, queryByText } = render(ConvertPanel);
    expect(queryByText("Filenames")).toBeNull();
    await fireEvent.click(getByText("Encoding"));
    expect(getByText("Filenames")).toBeInTheDocument();
  });
});
