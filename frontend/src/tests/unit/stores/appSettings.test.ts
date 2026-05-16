import { describe, it, expect, vi, beforeEach } from "vitest";
import { get } from "svelte/store";

vi.mock("$lib/api/settings", () => ({
  getAppSettings: vi.fn(),
  saveAppSettings: vi.fn().mockResolvedValue({ ok: true }),
}));

import { getAppSettings, saveAppSettings } from "$lib/api/settings";
import { appSettings, loadAppSettings, persistAppSettings } from "$lib/stores/appSettings";

const mockGet = vi.mocked(getAppSettings);
const mockSave = vi.mocked(saveAppSettings);

const SERVER_SETTINGS = {
  smart_extraction: false,
  trash_after_extract: true,
  default_output_dir: "/home/out",
  trash_after_create: true,
  trash_after_batch: false,
  default_password_encoding: "gbk",
  default_filename_encoding: "utf-8",
  notifications_enabled: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  // Reset store to defaults
  appSettings.set({
    smart_extraction: true,
    trash_after_extract: false,
    default_output_dir: "",
    trash_after_create: false,
    trash_after_batch: false,
    default_password_encoding: "",
    default_filename_encoding: "",
    notifications_enabled: true,
  });
});

describe("loadAppSettings", () => {
  it("calls getAppSettings and updates the store", async () => {
    mockGet.mockResolvedValue(SERVER_SETTINGS);
    await loadAppSettings();
    expect(mockGet).toHaveBeenCalled();
    expect(get(appSettings)).toEqual(SERVER_SETTINGS);
  });
});

describe("persistAppSettings", () => {
  it("merges patch into the store", async () => {
    mockGet.mockResolvedValue(SERVER_SETTINGS);
    await loadAppSettings();
    await persistAppSettings({ notifications_enabled: true });
    expect(get(appSettings).notifications_enabled).toBe(true);
    expect(get(appSettings).smart_extraction).toBe(false); // unchanged
  });

  it("calls saveAppSettings with the merged settings", async () => {
    mockGet.mockResolvedValue(SERVER_SETTINGS);
    await loadAppSettings();
    await persistAppSettings({ default_output_dir: "/new" });
    const saved = mockSave.mock.calls[0][0];
    expect(saved.default_output_dir).toBe("/new");
    expect(saved.smart_extraction).toBe(false);
  });
});
