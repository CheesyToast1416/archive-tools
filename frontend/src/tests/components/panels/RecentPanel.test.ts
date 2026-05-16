import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("@tauri-apps/plugin-fs", () => ({
  stat: vi.fn().mockResolvedValue({ mtime: new Date("2024-01-01").getTime() }),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue("/chosen/archive.zip"),
}));

const { uiStateStore, persistUIStateMock, addRecentMock, clearRecentsMock, pendingPathSet } =
  vi.hoisted(() => {
    const store = {
      subscribe: vi.fn((fn: (v: object) => void) => {
        fn({ theme: "system", active_nav: 0, recent_archives: [], last_archive_dir: "" });
        return () => {};
      }),
    };
    return {
      uiStateStore: store,
      persistUIStateMock: vi.fn().mockResolvedValue(undefined),
      addRecentMock: vi.fn().mockResolvedValue(undefined),
      clearRecentsMock: vi.fn().mockResolvedValue(undefined),
      pendingPathSet: vi.fn(),
    };
  });

vi.mock("$lib/stores/uiState", () => ({
  uiState: uiStateStore,
  persistUIState: persistUIStateMock,
  addRecent: addRecentMock,
  clearRecents: clearRecentsMock,
}));

vi.mock("$lib/stores/archive", () => ({
  pendingArchivePath: {
    set: pendingPathSet,
    subscribe: vi.fn((fn: (v: unknown) => void) => {
      fn(null);
      return () => {};
    }),
  },
}));

import RecentPanel from "$lib/components/panels/RecentPanel.svelte";
import { NAV_EXTRACT } from "$lib/constants";

function setRecents(paths: string[]) {
  uiStateStore.subscribe = vi.fn((fn: (v: object) => void) => {
    fn({ theme: "system", active_nav: 0, recent_archives: paths, last_archive_dir: "" });
    return () => {};
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  setRecents([]);
  persistUIStateMock.mockResolvedValue(undefined);
  addRecentMock.mockResolvedValue(undefined);
});

describe("RecentPanel", () => {
  it("shows empty state when no recent archives", () => {
    const { getByText } = render(RecentPanel);
    expect(getByText("No recent archives")).toBeInTheDocument();
  });

  it("shows browse button in empty state", () => {
    const { getAllByText } = render(RecentPanel);
    // Both the header button and the CTA button say "Browse Files" / "Open Archive…"
    expect(getAllByText(/Open Archive|Browse Files/).length).toBeGreaterThan(0);
  });

  it("renders archive cards for each recent path", () => {
    setRecents(["/home/user/test.zip", "/home/user/archive.rar"]);
    const { getByText } = render(RecentPanel);
    expect(getByText("test.zip")).toBeInTheDocument();
    expect(getByText("archive.rar")).toBeInTheDocument();
  });

  it("shows file extension badges on cards", () => {
    setRecents(["/home/user/test.zip"]);
    const { getByText } = render(RecentPanel);
    expect(getByText("ZIP")).toBeInTheDocument();
  });

  it("clicking a card calls addRecent and sets pendingArchivePath", async () => {
    setRecents(["/home/user/test.zip"]);
    const { getByText } = render(RecentPanel);
    await fireEvent.click(getByText("test.zip"));
    expect(addRecentMock).toHaveBeenCalledWith("/home/user/test.zip");
    expect(pendingPathSet).toHaveBeenCalledWith("/home/user/test.zip");
  });

  it("clicking a card navigates to Extract panel", async () => {
    setRecents(["/home/user/test.zip"]);
    const { getByText } = render(RecentPanel);
    await fireEvent.click(getByText("test.zip"));
    await waitFor(() =>
      expect(persistUIStateMock).toHaveBeenCalledWith({ active_nav: NAV_EXTRACT })
    );
  });

  it("shows Clear button when there are archives", () => {
    setRecents(["/home/user/test.zip"]);
    const { getByText } = render(RecentPanel);
    expect(getByText("Clear")).toBeInTheDocument();
  });

  it("Clear button calls clearRecents()", async () => {
    setRecents(["/home/user/test.zip"]);
    const { getByText } = render(RecentPanel);
    await fireEvent.click(getByText("Clear"));
    expect(clearRecentsMock).toHaveBeenCalled();
  });

  it("shows count badge", () => {
    setRecents(["/a.zip", "/b.zip", "/c.zip"]);
    const { getByText } = render(RecentPanel);
    expect(getByText("3")).toBeInTheDocument();
  });
});
