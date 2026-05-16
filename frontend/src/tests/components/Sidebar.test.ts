import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent } from "@testing-library/svelte";

const UI_STATE = { theme: "system", active_nav: 1, recent_archives: [], last_archive_dir: "" };
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

// vi.hoisted runs before vi.mock hoisting, so these are available in factory functions
const {
  persistUIStateMock,
  persistAppSettingsMock,
  applyThemeMock,
  uiStateStore,
  appSettingsStore,
} = vi.hoisted(() => {
  const uiStateStore = {
    subscribe: vi.fn((fn: (v: object) => void) => {
      fn(UI_STATE);
      return () => {};
    }),
  };
  const appSettingsStore = {
    subscribe: vi.fn((fn: (v: object) => void) => {
      fn(APP_SETTINGS);
      return () => {};
    }),
  };
  return {
    persistUIStateMock: vi.fn().mockResolvedValue(undefined),
    persistAppSettingsMock: vi.fn().mockResolvedValue(undefined),
    applyThemeMock: vi.fn(),
    uiStateStore,
    appSettingsStore,
  };
});

vi.mock("$lib/stores/uiState", () => ({
  uiState: uiStateStore,
  persistUIState: persistUIStateMock,
  applyTheme: applyThemeMock,
}));

vi.mock("$lib/stores/appSettings", () => ({
  appSettings: appSettingsStore,
  persistAppSettings: persistAppSettingsMock,
}));

vi.mock("$lib/api/passwords", () => ({
  listPasswords: vi.fn().mockResolvedValue([]),
  getKeyringStatus: vi.fn().mockResolvedValue({ keyring_available: true }),
  addPassword: vi.fn(),
  deletePassword: vi.fn(),
  getPasswordSecret: vi.fn().mockResolvedValue({ password: "" }),
  updatePassword: vi.fn(),
}));

vi.mock("@tauri-apps/api/app", () => ({
  getVersion: vi.fn().mockResolvedValue("0.2.0"),
}));

import Sidebar from "$lib/components/Sidebar.svelte";
import { NAV_EXTRACT, NAV_CREATE, NAV_BATCH } from "$lib/constants";

beforeEach(() => {
  vi.clearAllMocks();
  uiStateStore.subscribe = vi.fn((fn: (v: object) => void) => {
    fn(UI_STATE);
    return () => {};
  });
  appSettingsStore.subscribe = vi.fn((fn: (v: object) => void) => {
    fn(APP_SETTINGS);
    return () => {};
  });
  persistUIStateMock.mockResolvedValue(undefined);
  persistAppSettingsMock.mockResolvedValue(undefined);
});

describe("Sidebar", () => {
  it("renders all 5 nav items", () => {
    const { getByText } = render(Sidebar);
    expect(getByText("Recent")).toBeInTheDocument();
    expect(getByText("Extract")).toBeInTheDocument();
    expect(getByText("Create")).toBeInTheDocument();
    expect(getByText("Batch")).toBeInTheDocument();
    expect(getByText("Convert")).toBeInTheDocument();
  });

  it("renders the ArchiveTools brand", () => {
    const { getByText } = render(Sidebar);
    expect(getByText("ArchiveTools")).toBeInTheDocument();
  });

  it("clicking a nav item calls persistUIState with the correct nav index", async () => {
    const { getByText } = render(Sidebar);
    await fireEvent.click(getByText("Create"));
    expect(persistUIStateMock).toHaveBeenCalledWith({ active_nav: NAV_CREATE });
  });

  it("clicking Batch nav item calls persistUIState with NAV_BATCH", async () => {
    const { getByText } = render(Sidebar);
    await fireEvent.click(getByText("Batch"));
    expect(persistUIStateMock).toHaveBeenCalledWith({ active_nav: NAV_BATCH });
  });

  it("settings gear icon opens SettingsDialog", async () => {
    const { getByTitle, findByText } = render(Sidebar);
    await fireEvent.click(getByTitle("Settings"));
    expect(await findByText("Preferences")).toBeInTheDocument();
  });

  it("password key icon opens PasswordManager", async () => {
    const { getByTitle, findByText } = render(Sidebar);
    await fireEvent.click(getByTitle("Saved Passwords"));
    // Dialog title (h2 level) also says "Saved Passwords"
    const matches = await findByText("Saved Passwords");
    expect(matches).toBeInTheDocument();
  });

  it("clicking Extract item navigates to extract panel", async () => {
    const { getByText } = render(Sidebar);
    await fireEvent.click(getByText("Extract"));
    expect(persistUIStateMock).toHaveBeenCalledWith({ active_nav: NAV_EXTRACT });
  });
});
