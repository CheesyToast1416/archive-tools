import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("$lib/api/client", () => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
}));

import { apiGet, apiPut } from "$lib/api/client";
import { getAppSettings, saveAppSettings, getUIState, saveUIState } from "$lib/api/settings";

const get = vi.mocked(apiGet);
const put = vi.mocked(apiPut);

const APP_SETTINGS = {
  smart_extraction: true,
  trash_after_extract: false,
  default_output_dir: "",
  trash_after_create: false,
  trash_after_batch: false,
  default_password_encoding: "",
  default_filename_encoding: "",
  notifications_enabled: true,
};

const UI_STATE = {
  theme: "system",
  active_nav: 1,
  recent_archives: [],
  last_archive_dir: "",
};

beforeEach(() => {
  vi.clearAllMocks();
  get.mockResolvedValue(APP_SETTINGS);
  put.mockResolvedValue({ ok: true });
});

describe("getAppSettings", () => {
  it("GETs /settings/app", async () => {
    const r = await getAppSettings();
    expect(get).toHaveBeenCalledWith("/settings/app");
    expect(r).toEqual(APP_SETTINGS);
  });
});

describe("saveAppSettings", () => {
  it("PUTs to /settings/app with full settings object", async () => {
    await saveAppSettings(APP_SETTINGS);
    expect(put).toHaveBeenCalledWith("/settings/app", APP_SETTINGS);
  });
});

describe("getUIState", () => {
  it("GETs /settings/ui", async () => {
    get.mockResolvedValue(UI_STATE);
    const r = await getUIState();
    expect(get).toHaveBeenCalledWith("/settings/ui");
    expect(r).toEqual(UI_STATE);
  });
});

describe("saveUIState", () => {
  it("PUTs to /settings/ui", async () => {
    await saveUIState(UI_STATE as Parameters<typeof saveUIState>[0]);
    expect(put).toHaveBeenCalledWith("/settings/ui", UI_STATE);
  });
});
