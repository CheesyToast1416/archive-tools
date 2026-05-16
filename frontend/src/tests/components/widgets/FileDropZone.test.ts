import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent } from "@testing-library/svelte";

vi.mock("@tauri-apps/api/webviewWindow", () => ({
  getCurrentWebviewWindow: () => ({
    onDragDropEvent: vi.fn().mockResolvedValue(() => {}),
  }),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockResolvedValue("/selected/archive.zip"),
}));

import { open } from "@tauri-apps/plugin-dialog";
import FileDropZone from "$lib/components/widgets/FileDropZone.svelte";

const mockOpen = vi.mocked(open);

beforeEach(() => vi.clearAllMocks());

describe("FileDropZone", () => {
  it("renders hint text", () => {
    const { getByText } = render(FileDropZone);
    expect(getByText("Drop an archive here")).toBeInTheDocument();
  });

  it("renders Browse Files button", () => {
    const { getByText } = render(FileDropZone);
    expect(getByText("Browse Files")).toBeInTheDocument();
  });

  it("clicking Browse Files opens dialog and dispatches path event", async () => {
    const handler = vi.fn();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { getByText } = render(FileDropZone as any, { events: { path: handler } });
    await fireEvent.click(getByText("Browse Files"));
    expect(mockOpen).toHaveBeenCalled();
    await vi.waitFor(() =>
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({ detail: "/selected/archive.zip" })
      )
    );
  });

  it("does not dispatch path event if dialog is cancelled (returns null)", async () => {
    mockOpen.mockResolvedValueOnce(null);
    const handler = vi.fn();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { getByText } = render(FileDropZone as any, { events: { path: handler } });
    await fireEvent.click(getByText("Browse Files"));
    await vi.waitFor(() => expect(mockOpen).toHaveBeenCalled());
    expect(handler).not.toHaveBeenCalled();
  });
});
