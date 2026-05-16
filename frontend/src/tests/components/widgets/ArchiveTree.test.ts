import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/svelte";

vi.mock("@tauri-apps/api/webviewWindow", () => ({
  getCurrentWebviewWindow: () => ({
    onDragDropEvent: vi.fn().mockResolvedValue(() => {}),
  }),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue(["/dropped/file.txt"]),
}));

import ArchiveTree from "$lib/components/widgets/ArchiveTree.svelte";

const FLAT_NAMES = ["a.txt", "b.png", "c.zip"];
const NESTED_NAMES = [
  "docs/",
  "docs/readme.md",
  "docs/guide.pdf",
  "src/",
  "src/main.py",
  "icon.png",
];

describe("ArchiveTree", () => {
  it("shows entry count 0 for empty names", () => {
    const { getByText } = render(ArchiveTree, { props: { names: [] } });
    expect(getByText("0")).toBeInTheDocument();
  });

  it("shows correct entry count", () => {
    const { getByText } = render(ArchiveTree, { props: { names: FLAT_NAMES } });
    expect(getByText(String(FLAT_NAMES.length))).toBeInTheDocument();
  });

  it("renders file rows for flat list", () => {
    const { getByText } = render(ArchiveTree, { props: { names: FLAT_NAMES } });
    expect(getByText("a.txt")).toBeInTheDocument();
    expect(getByText("b.png")).toBeInTheDocument();
    expect(getByText("c.zip")).toBeInTheDocument();
  });

  it("renders directory nodes for nested paths", () => {
    const { getByText } = render(ArchiveTree, { props: { names: NESTED_NAMES } });
    expect(getByText("docs")).toBeInTheDocument();
    expect(getByText("src")).toBeInTheDocument();
  });

  it("expands directory on click to show children", async () => {
    const { getByText, queryByText } = render(ArchiveTree, { props: { names: NESTED_NAMES } });
    // Children hidden initially in large trees — but NESTED_NAMES has 6 entries (<= 50)
    // so dirs start expanded. Collapse by clicking, then re-expand.
    const docsNode = getByText("docs");
    await fireEvent.click(docsNode); // collapse
    expect(queryByText("readme.md")).toBeNull();
    await fireEvent.click(docsNode); // expand
    expect(getByText("readme.md")).toBeInTheDocument();
  });

  it("dispatches entrySelected event when a file is clicked", async () => {
    const handler = vi.fn();
    // Svelte 5: createEventDispatcher uses $$events callbacks, not DOM events
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { getByText } = render(ArchiveTree as any, {
      props: { names: FLAT_NAMES },
      events: { entrySelected: handler },
    });
    await fireEvent.click(getByText("a.txt"));
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ detail: "a.txt" }));
  });

  it("does not dispatch entrySelected for directory clicks", async () => {
    const handler = vi.fn();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { getByText } = render(ArchiveTree as any, {
      props: { names: NESTED_NAMES },
      events: { entrySelected: handler },
    });
    await fireEvent.click(getByText("docs"));
    expect(handler).not.toHaveBeenCalled();
  });

  it("shows Add Files button in edit mode", () => {
    const { getByText } = render(ArchiveTree, { props: { names: [], editMode: true } });
    expect(getByText("Add Files")).toBeInTheDocument();
  });

  it("hides Add Files button outside edit mode", () => {
    const { queryByText } = render(ArchiveTree, { props: { names: [], editMode: false } });
    expect(queryByText("Add Files")).toBeNull();
  });

  it("large tree (>50 entries) starts with dirs collapsed", () => {
    // 30 dirs × 2 entries each = 60 total entries — triggers collapsed start
    const large = Array.from({ length: 30 }, (_, i) => [
      `dir${i}/`,
      `dir${i}/unique${i}.txt`,
    ]).flat();
    const { queryAllByText } = render(ArchiveTree, { props: { names: large } });
    // All children should be hidden because dirs start collapsed for large trees
    expect(queryAllByText(/^unique\d+\.txt$/).length).toBe(0);
  });
});
