<script lang="ts">
  import { Image, Info, LayoutGrid } from "@lucide/svelte";
  import { convertFileSrc } from "@tauri-apps/api/core";
  import { formatBytes } from "$lib/constants";
  import type { InfoResponse } from "$lib/api/archives";

  export let entryPath: string | null = null;
  export let filePath: string | null = null;
  /** Pre-built URL (with auth token as query param) for fetching / playing file content. */
  export let serveUrl: string | null = null;
  export let archiveInfo: InfoResponse | null = null;
  export let loading = false;

  type Mode = "preview" | "info";
  let mode: Mode = "preview";

  const IMAGE_EXTS = new Set(["jpg", "jpeg", "png", "gif", "bmp", "webp", "ico", "tiff", "svg"]);
  const TEXT_EXTS = new Set([
    "txt",
    "md",
    "py",
    "js",
    "ts",
    "css",
    "html",
    "xml",
    "json",
    "yaml",
    "yml",
    "toml",
    "ini",
    "cfg",
    "conf",
    "log",
    "sh",
    "bash",
    "diff",
    "patch",
    "rst",
    "csv",
    "c",
    "h",
    "cpp",
    "java",
    "rb",
    "go",
    "zsh",
    "fish",
    "rs",
    "kt",
    "swift",
    "php",
  ]);
  const PDF_EXTS = new Set(["pdf"]);
  const AUDIO_EXTS = new Set(["mp3", "wav", "ogg", "flac", "aac", "m4a", "opus", "wma"]);
  const VIDEO_EXTS = new Set(["mp4", "webm", "mov", "m4v"]);
  const NO_PREVIEW_EXTS = new Set(["mkv", "avi", "flv", "wmv"]);

  $: ext = entryPath ? (entryPath.split(".").pop()?.toLowerCase() ?? "") : "";
  $: assetUrl = filePath ? convertFileSrc(filePath) : null;

  $: previewKind = (() => {
    if (!ext) return "none";
    if (IMAGE_EXTS.has(ext)) return "image";
    if (TEXT_EXTS.has(ext)) return "text";
    if (PDF_EXTS.has(ext)) return "pdf";
    if (AUDIO_EXTS.has(ext)) return "audio";
    if (VIDEO_EXTS.has(ext)) return "video";
    if (NO_PREVIEW_EXTS.has(ext)) return "unsupported";
    return "none";
  })();

  let textContent = "";
  $: if (serveUrl && previewKind === "text") {
    fetch(serveUrl)
      .then((r) => r.text())
      .then((t) => {
        // eslint-disable-next-line svelte/infinite-reactive-loop
        textContent = t.slice(0, 100_000);
      })
      .catch(() => {
        // eslint-disable-next-line svelte/infinite-reactive-loop
        textContent = "(Could not read file)";
      });
  } else if (!serveUrl) {
    textContent = "";
  }

  const entryName = (p: string | null) => (p ? (p.split("/").pop() ?? p) : "");

  // Detect missing H.264+AAC support (the most common MP4 codec pair).
  // Only checks MP4 — WebM may work on Linux while AAC still fails.
  const _probe = typeof document !== "undefined" ? document.createElement("video") : null;
  const videoAudioSupported = _probe
    ? _probe.canPlayType('video/mp4; codecs="avc1.42E01E, mp4a.40.2"') !== ""
    : true;

  $: ratioStr = (() => {
    if (!archiveInfo || archiveInfo.uncompressed_size <= 0) return "—";
    const r = 1 - archiveInfo.compressed_size / archiveInfo.uncompressed_size;
    return `${Math.round(r * 100)}%`;
  })();
</script>

<div class="pane">
  <div class="pane-header">
    <!-- Pill toggle -->
    <div class="pill-toggle" role="group">
      <button class="pill-btn" class:active={mode === "preview"} onclick={() => (mode = "preview")}>
        <Image size={12} />
        Preview
      </button>
      <button class="pill-btn" class:active={mode === "info"} onclick={() => (mode = "info")}>
        <Info size={12} />
        Info
      </button>
    </div>
    {#if entryPath && mode === "preview"}
      <span class="entry-label" title={entryPath}>{entryName(entryPath)}</span>
    {/if}
  </div>

  <div class="pane-body">
    {#if loading}
      <div class="placeholder">
        <div class="mini-spinner"></div>
      </div>
    {:else if mode === "info"}
      {#if archiveInfo}
        <div class="info-grid">
          <div class="info-row">
            <span class="info-key">Format</span><span class="info-val"
              >{archiveInfo.format_name}</span
            >
          </div>
          <div class="info-row">
            <span class="info-key">Files</span><span class="info-val"
              >{archiveInfo.file_count < 0 ? "—" : archiveInfo.file_count}</span
            >
          </div>
          <div class="info-row">
            <span class="info-key">Compressed</span><span class="info-val"
              >{formatBytes(archiveInfo.compressed_size)}</span
            >
          </div>
          <div class="info-row">
            <span class="info-key">Original</span><span class="info-val"
              >{formatBytes(archiveInfo.uncompressed_size)}</span
            >
          </div>
          <div class="info-row">
            <span class="info-key">Ratio</span><span class="info-val">{ratioStr}</span>
          </div>
          <div class="info-row">
            <span class="info-key">Encrypted</span><span class="info-val"
              >{archiveInfo.is_encrypted ? "Yes" : "No"}</span
            >
          </div>
          {#if archiveInfo.comment}
            <div class="info-row full">
              <span class="info-key">Comment</span><span class="info-val"
                >{archiveInfo.comment}</span
              >
            </div>
          {/if}
        </div>
      {:else}
        <div class="placeholder">
          <LayoutGrid size={28} strokeWidth={1.2} />
          <span>Open an archive to see info</span>
        </div>
      {/if}
    {:else if !entryPath}
      <div class="placeholder">
        <Image size={28} strokeWidth={1.2} />
        <span>Select a file to preview</span>
      </div>
    {:else if !filePath}
      <div class="placeholder">
        <div class="mini-spinner"></div>
        <span>Loading preview…</span>
      </div>
    {:else if previewKind === "image"}
      <img src={assetUrl} alt={entryName(entryPath)} class="preview-img" />
    {:else if previewKind === "text"}
      <pre class="preview-text">{textContent}</pre>
    {:else if previewKind === "pdf"}
      <iframe src={assetUrl} title="PDF preview" class="preview-iframe"></iframe>
    {:else if previewKind === "audio"}
      <audio controls src={serveUrl ?? undefined} class="preview-audio"></audio>
    {:else if previewKind === "video"}
      <!-- svelte-ignore a11y-media-has-caption -->
      <video controls src={serveUrl ?? undefined} class="preview-video"></video>
      {#if !videoAudioSupported}
        <p class="codec-hint">No audio codec — install <code>gst-libav</code></p>
      {/if}
    {:else if previewKind === "unsupported"}
      <div class="placeholder">
        <span>Unsupported format</span>
        <span class="placeholder-sub">Extract and open externally</span>
      </div>
    {:else}
      <div class="placeholder">
        <Image size={28} strokeWidth={1.2} />
        <span>No preview available</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .pane {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-left: 1px solid var(--glass-border);
  }

  /* ── Header ──────────────────────────────────────────────── */

  .pane-header {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 12px 8px;
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }

  /* Pill toggle */
  .pill-toggle {
    display: flex;
    background: var(--glass-inset);
    border-radius: 8px;
    padding: 2px;
    gap: 2px;
  }

  .pill-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    flex: 1;
    padding: 5px 10px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-2);
    font-size: 12px;
    font-family: var(--font-sans) sans-serif;
    font-weight: 500;
    cursor: pointer;
    justify-content: center;
    transition:
      background 0.15s,
      color 0.15s,
      box-shadow 0.15s;
  }

  .pill-btn.active {
    background: var(--glass-raised);
    color: var(--text);
    box-shadow: var(--shadow-sm);
  }

  .entry-label {
    font-size: 11px;
    color: var(--text-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding: 0 2px;
  }

  /* ── Body ────────────────────────────────────────────────── */

  .pane-body {
    flex: 1;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    padding: 8px;
  }

  /* ── Placeholder ─────────────────────────────────────────── */

  .placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    color: var(--text-3);
    font-size: 13px;
    text-align: center;
    padding: 24px;
  }

  .placeholder-sub {
    font-size: 11px;
    color: var(--text-3);
  }

  .mini-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--glass-border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ── Media previews ──────────────────────────────────────── */

  .preview-img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    padding: 12px;
  }

  .preview-text {
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 12px 14px;
    font-family: var(--font-mono) sans-serif;
    font-size: 11px;
    overflow: auto;
    color: var(--text);
    line-height: 1.65;
    background: transparent;
    align-self: flex-start;
  }

  .preview-iframe {
    width: 100%;
    height: 100%;
    border: none;
  }

  .preview-audio {
    width: 80%;
  }

  .preview-video {
    max-width: 100%;
    max-height: 100%;
  }

  .codec-hint {
    position: absolute;
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
    margin: 0;
    font-size: 11px;
    color: var(--warning);
    background: var(--warning-subtle, rgba(255, 159, 10, 0.12));
    border: 1px solid rgba(255, 159, 10, 0.25);
    border-radius: 6px;
    padding: 4px 10px;
    white-space: nowrap;
    pointer-events: none;
  }

  .codec-hint code {
    font-family: var(--font-mono) sans-serif;
    background: transparent;
  }

  /* ── Info grid ───────────────────────────────────────────── */

  .info-grid {
    width: 100%;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    align-self: flex-start;
  }

  .info-row {
    display: flex;
    align-items: baseline;
    padding: 6px 10px;
    border-radius: 8px;
    transition: background 0.1s;
  }

  .info-row:hover {
    background: var(--glass-inset);
  }

  .info-key {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    width: 90px;
    flex-shrink: 0;
  }

  .info-val {
    font-size: 13px;
    color: var(--text);
    word-break: break-word;
  }
</style>
