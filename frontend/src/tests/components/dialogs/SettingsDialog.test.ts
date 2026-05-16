import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent } from "@testing-library/svelte";

vi.mock("@tauri-apps/api/app", () => ({
  getVersion: vi.fn().mockResolvedValue("0.2.0"),
}));

vi.mock("$lib/stores/appSettings", () => ({
  appSettings: {
    subscribe: vi.fn((fn: (v: object) => void) => {
      fn(DEFAULT_SETTINGS);
      return () => {};
    }),
  },
  persistAppSettings: vi.fn().mockResolvedValue(undefined),
}));

const DEFAULT_SETTINGS = {
  smart_extraction: true,
  trash_after_extract: false,
  default_output_dir: "",
  trash_after_create: false,
  trash_after_batch: false,
  default_password_encoding: "",
  default_filename_encoding: "",
  notifications_enabled: true,
};

import { persistAppSettings } from "$lib/stores/appSettings";
import SettingsDialog from "$lib/components/dialogs/SettingsDialog.svelte";

const mockPersist = vi.mocked(persistAppSettings);

beforeEach(() => vi.clearAllMocks());

describe("SettingsDialog", () => {
  it("renders all setting sections", () => {
    const { getByText } = render(SettingsDialog, { props: { close: vi.fn() } });
    expect(getByText("Extraction")).toBeInTheDocument();
    expect(getByText("Archive Creation")).toBeInTheDocument();
    expect(getByText("Encoding Defaults")).toBeInTheDocument();
    expect(getByText("Notifications")).toBeInTheDocument();
  });

  it("shows version in footer", async () => {
    const { findByText } = render(SettingsDialog, { props: { close: vi.fn() } });
    expect(await findByText("v0.2.0")).toBeInTheDocument();
  });

  it("renders toggles for boolean settings", () => {
    const { getByText } = render(SettingsDialog, { props: { close: vi.fn() } });
    expect(getByText("Smart extraction")).toBeInTheDocument();
    expect(getByText("Desktop notifications")).toBeInTheDocument();
  });

  it("Save Changes calls persistAppSettings and dispatches close", async () => {
    const closeHandler = vi.fn();
    const { getByText } = render(SettingsDialog, { props: { close: closeHandler } });
    await fireEvent.click(getByText("Save Changes"));
    expect(mockPersist).toHaveBeenCalled();
    await vi.waitFor(() => expect(closeHandler).toHaveBeenCalled());
  });

  it("Cancel dispatches close without saving", async () => {
    const closeHandler = vi.fn();
    const { getByText } = render(SettingsDialog, { props: { close: closeHandler } });
    await fireEvent.click(getByText("Cancel"));
    expect(mockPersist).not.toHaveBeenCalled();
    expect(closeHandler).toHaveBeenCalled();
  });

  it("X button in header dispatches close", async () => {
    const closeHandler = vi.fn();
    const { container } = render(SettingsDialog, { props: { close: closeHandler } });
    await fireEvent.click(container.querySelector(".close-btn")!);
    expect(closeHandler).toHaveBeenCalled();
  });

  it("toggling smart_extraction checkbox updates draft", async () => {
    const { getByText } = render(SettingsDialog, {
      events: { close: vi.fn() },
    } as never);
    // The smart extraction toggle should be checked (default is true)
    const smartExtractionRow = getByText("Smart extraction").closest(".setting-row")!;
    const toggle = smartExtractionRow.querySelector("input[type=checkbox]") as HTMLInputElement;
    expect(toggle.checked).toBe(true);
    await fireEvent.click(toggle);
    expect(toggle.checked).toBe(false);
  });
});
