import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor } from "@testing-library/svelte";
import PreviewPane from "$lib/components/widgets/PreviewPane.svelte";
import type { InfoResponse } from "$lib/api/archives";

// Return about:blank so happy-dom doesn't attempt any network fetch
vi.mock("@tauri-apps/api/core", () => ({
  convertFileSrc: vi.fn(() => "about:blank"),
}));

const INFO: InfoResponse = {
  format_name: "ZIP",
  file_count: 5,
  compressed_size: 1024,
  uncompressed_size: 4096,
  is_encrypted: false,
  comment: "",
};

beforeEach(() => {
  vi.spyOn(global, "fetch").mockResolvedValue(new Response("file text content", { status: 200 }));
});

afterEach(() => vi.restoreAllMocks());

describe("PreviewPane", () => {
  it("shows 'Select a file to preview' placeholder with no entry", () => {
    const { getByText } = render(PreviewPane);
    expect(getByText("Select a file to preview")).toBeInTheDocument();
  });

  it("preview/info pill toggle switches mode", async () => {
    const { getByText } = render(PreviewPane, {
      props: { archiveInfo: INFO },
    });
    await fireEvent.click(getByText("Info"));
    expect(getByText("ZIP")).toBeInTheDocument(); // format name from archiveInfo
  });

  it("info mode shows archive metadata", async () => {
    const { getByText } = render(PreviewPane, {
      props: { archiveInfo: INFO },
    });
    await fireEvent.click(getByText("Info"));
    expect(getByText("ZIP")).toBeInTheDocument();
    expect(getByText("5")).toBeInTheDocument();
    expect(getByText("No")).toBeInTheDocument(); // is_encrypted
  });

  it("shows 'Open an archive to see info' when no archiveInfo in info mode", async () => {
    const { getByText } = render(PreviewPane);
    await fireEvent.click(getByText("Info"));
    expect(getByText("Open an archive to see info")).toBeInTheDocument();
  });

  it("shows loading spinner when filePath is null but entryPath set", () => {
    const { getByText } = render(PreviewPane, {
      props: { entryPath: "photo.jpg", filePath: null },
    });
    expect(getByText("Loading preview…")).toBeInTheDocument();
  });

  it("renders img for image files", () => {
    const { container } = render(PreviewPane, {
      props: { entryPath: "photo.jpg", filePath: "/tmp/photo.jpg", serveUrl: "http://x/serve" },
    });
    expect(container.querySelector("img")).toBeInTheDocument();
  });

  it("renders audio element for audio files", () => {
    const { container } = render(PreviewPane, {
      props: { entryPath: "song.mp3", filePath: "/tmp/song.mp3", serveUrl: "http://x/serve" },
    });
    expect(container.querySelector("audio")).toBeInTheDocument();
  });

  it("renders video element for video files", () => {
    const { container } = render(PreviewPane, {
      props: { entryPath: "clip.mp4", filePath: "/tmp/clip.mp4", serveUrl: "http://x/serve" },
    });
    expect(container.querySelector("video")).toBeInTheDocument();
  });

  it("renders iframe for PDF files", () => {
    const { container } = render(PreviewPane, {
      props: { entryPath: "doc.pdf", filePath: "/tmp/doc.pdf", serveUrl: "http://x/serve" },
    });
    expect(container.querySelector("iframe")).toBeInTheDocument();
  });

  it("fetches and renders text content", async () => {
    const { container } = render(PreviewPane, {
      props: { entryPath: "readme.txt", filePath: "/tmp/readme.txt", serveUrl: "http://x/serve" },
    });
    await waitFor(() => {
      expect(container.querySelector("pre")?.textContent).toContain("file text content");
    });
  });

  it("shows 'Unsupported format' for mkv files", () => {
    const { getByText } = render(PreviewPane, {
      props: { entryPath: "video.mkv", filePath: "/tmp/video.mkv", serveUrl: "http://x/serve" },
    });
    expect(getByText("Unsupported format")).toBeInTheDocument();
  });

  it("shows 'No preview available' for unknown extensions", () => {
    const { getByText } = render(PreviewPane, {
      props: { entryPath: "file.xyz", filePath: "/tmp/file.xyz", serveUrl: "http://x/serve" },
    });
    expect(getByText("No preview available")).toBeInTheDocument();
  });

  it("shows loading placeholder when loading prop is true", () => {
    const { container } = render(PreviewPane, { props: { loading: true } });
    expect(container.querySelector(".mini-spinner")).toBeInTheDocument();
  });
});
