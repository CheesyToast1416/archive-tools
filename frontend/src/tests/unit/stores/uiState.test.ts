import { describe, it, expect, vi, beforeEach } from "vitest";
import { get } from "svelte/store";

vi.mock("$lib/api/settings", () => ({
  getUIState: vi.fn(),
  saveUIState: vi.fn().mockResolvedValue({ ok: true }),
}));

import { getUIState, saveUIState } from "$lib/api/settings";
import {
  uiState,
  loadUIState,
  persistUIState,
  addRecent,
  clearRecents,
  applyTheme,
} from "$lib/stores/uiState";

const mockGet = vi.mocked(getUIState);
const mockSave = vi.mocked(saveUIState);

const SERVER_STATE = {
  theme: "dark" as const,
  active_nav: 2,
  recent_archives: ["/home/a.zip", "/home/b.rar"],
  last_archive_dir: "/home",
};

function resetStore() {
  uiState.set({ theme: "system", active_nav: 1, recent_archives: [], last_archive_dir: "" });
}

beforeEach(() => {
  vi.clearAllMocks();
  resetStore();
});

describe("loadUIState", () => {
  it("calls getUIState and updates the store", async () => {
    mockGet.mockResolvedValue(SERVER_STATE);
    await loadUIState();
    expect(get(uiState)).toEqual(SERVER_STATE);
  });

  it("calls applyTheme with the loaded theme", async () => {
    mockGet.mockResolvedValue(SERVER_STATE);
    await loadUIState();
    // dark theme → document should have 'dark' class
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});

describe("persistUIState", () => {
  it("merges patch into the store", async () => {
    await persistUIState({ active_nav: 3 });
    expect(get(uiState).active_nav).toBe(3);
  });

  it("calls saveUIState with the merged state", async () => {
    await persistUIState({ active_nav: 4 });
    expect(mockSave).toHaveBeenCalledWith(expect.objectContaining({ active_nav: 4 }));
  });
});

describe("addRecent", () => {
  it("prepends new path to the front", async () => {
    uiState.set({ ...get(uiState), recent_archives: ["/a.zip"] });
    await addRecent("/b.zip");
    expect(get(uiState).recent_archives[0]).toBe("/b.zip");
  });

  it("deduplicates: existing path moves to front", async () => {
    uiState.set({ ...get(uiState), recent_archives: ["/a.zip", "/b.zip"] });
    await addRecent("/b.zip");
    const recents = get(uiState).recent_archives;
    expect(recents[0]).toBe("/b.zip");
    expect(recents.filter((p) => p === "/b.zip").length).toBe(1);
  });

  it("trims list to 15 entries", async () => {
    const existing = Array.from({ length: 15 }, (_, i) => `/file${i}.zip`);
    uiState.set({ ...get(uiState), recent_archives: existing });
    await addRecent("/new.zip");
    expect(get(uiState).recent_archives.length).toBe(15);
    expect(get(uiState).recent_archives[0]).toBe("/new.zip");
  });
});

describe("clearRecents", () => {
  it("empties the recent_archives list", async () => {
    uiState.set({ ...get(uiState), recent_archives: ["/a.zip", "/b.zip"] });
    await clearRecents();
    expect(get(uiState).recent_archives).toEqual([]);
  });
});

describe("applyTheme", () => {
  it("adds 'dark' class for dark theme", () => {
    applyTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes 'dark' class for light theme", () => {
    document.documentElement.classList.add("dark");
    applyTheme("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("uses system preference for 'system' theme", () => {
    // matchMedia is mocked to return matches: false (light mode)
    applyTheme("system");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
