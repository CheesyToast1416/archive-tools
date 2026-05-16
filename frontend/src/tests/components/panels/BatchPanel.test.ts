import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("@tauri-apps/api/webviewWindow", () => ({
  getCurrentWebviewWindow: () => ({ onDragDropEvent: vi.fn().mockResolvedValue(() => {}) }),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue(["/home/user/a.zip", "/home/user/b.rar"]),
}));

// batchExtract mock: immediately calls complete handler
vi.mock("$lib/api/archives", () => ({
  batchExtract: vi.fn().mockImplementation((_params, handlers) => {
    handlers.archive_started?.({ index: 0 });
    handlers.archive_done?.({ index: 0, ok: true, detail: "" });
    handlers.archive_started?.({ index: 1 });
    handlers.archive_done?.({ index: 1, ok: false, detail: "bad archive" });
    handlers.complete?.({ ok_count: 1, fail_count: 1 });
    return Promise.resolve();
  }),
}));

const { appSettingsStore } = vi.hoisted(() => ({
  appSettingsStore: {
    subscribe: vi.fn((fn: (v: object) => void) => {
      fn({
        default_filename_encoding: "",
        default_password_encoding: "",
        trash_after_batch: false,
        smart_extraction: true,
        trash_after_extract: false,
        default_output_dir: "",
        trash_after_create: false,
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

import { batchExtract } from "$lib/api/archives";
import BatchPanel from "$lib/components/panels/BatchPanel.svelte";

beforeEach(() => vi.clearAllMocks());

describe("BatchPanel", () => {
  it("shows empty table placeholder initially", () => {
    const { getByText } = render(BatchPanel);
    expect(getByText("No archives — drag files here or use Add Archives")).toBeInTheDocument();
  });

  it("Add Archives button opens dialog", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const { getByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    expect(open).toHaveBeenCalled();
  });

  it("adds archives from dialog to the table", async () => {
    const { getByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => {
      expect(getByText("a.zip")).toBeInTheDocument();
      expect(getByText("b.rar")).toBeInTheDocument();
    });
  });

  it("shows Pending status for new archives", async () => {
    const { getByText, getAllByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => getAllByText("Pending"));
    expect(getAllByText("Pending").length).toBe(2);
  });

  it("Clear button removes all archives", async () => {
    const { getByText, queryByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => getByText("a.zip"));
    await fireEvent.click(getByText("Clear"));
    expect(queryByText("a.zip")).toBeNull();
  });

  it("Extract All calls batchExtract", async () => {
    const { getByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => getByText("a.zip"));
    await fireEvent.click(getByText("Extract All"));
    await waitFor(() => expect(batchExtract).toHaveBeenCalled());
  });

  it("shows Done/Failed status after extraction", async () => {
    const { getByText, findByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => getByText("a.zip"));
    await fireEvent.click(getByText("Extract All"));
    expect(await findByText("✓ Done")).toBeInTheDocument();
    expect(await findByText("✗ Failed")).toBeInTheDocument();
  });

  it("shows completion summary in log", async () => {
    const { getByText, findByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => getByText("a.zip"));
    await fireEvent.click(getByText("Extract All"));
    await waitFor(() => getByText("Log"));
    await fireEvent.click(getByText("Log"));
    expect(await findByText(/1 succeeded/)).toBeInTheDocument();
  });

  it("shows archive counter fraction", async () => {
    const { getByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => getByText("a.zip"));
    // Before extraction: 0/2
    expect(getByText("0 / 2")).toBeInTheDocument();
  });

  it("checkbox selects rows, Remove removes them", async () => {
    const { getByText, getAllByRole, queryByText } = render(BatchPanel);
    await fireEvent.click(getByText("Add Archives"));
    await waitFor(() => getByText("a.zip"));
    const checkboxes = getAllByRole("checkbox");
    await fireEvent.click(checkboxes[0]);
    await fireEvent.click(getByText(/Remove \(1\)/));
    expect(queryByText("a.zip")).toBeNull();
    expect(getByText("b.rar")).toBeInTheDocument();
  });

  it("shows encoding toggle section", async () => {
    const { getByText, queryByText } = render(BatchPanel);
    expect(queryByText("Filenames")).toBeNull();
    await fireEvent.click(getByText("Encoding"));
    expect(getByText("Filenames")).toBeInTheDocument();
  });
});
