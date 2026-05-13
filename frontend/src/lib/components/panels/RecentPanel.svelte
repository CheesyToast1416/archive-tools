<script lang="ts">
  import { onMount } from "svelte";
  import { Archive, FolderOpen, Trash2 } from "lucide-svelte";
  import { stat } from "@tauri-apps/plugin-fs";
  import { open } from "@tauri-apps/plugin-dialog";
  import { uiState, addRecent, clearRecents, persistUIState } from "../../stores/uiState";
  import { pendingArchivePath } from "../../stores/archive";
  import { NAV_EXTRACT, ARCHIVE_EXTENSIONS, relativeTime } from "../../constants";

  let mtimes: Record<string, Date | null> = {};

  $: paths = $uiState.recent_archives;

  $: loadMtimes(paths);

  async function loadMtimes(ps: string[]) {
    for (const p of ps) {
      if (!(p in mtimes)) {
        const info = await stat(p).catch(() => null);
        mtimes[p] = info?.mtime ? new Date(info.mtime) : null;
        mtimes = mtimes;
      }
    }
  }

  function archiveName(path: string): string {
    return path.split(/[\\/]/).pop() ?? path;
  }

  function archiveExt(path: string): string {
    return path.split(".").pop()?.toUpperCase() ?? "ZIP";
  }

  async function openCard(path: string) {
    await addRecent(path);
    pendingArchivePath.set(path);
    await persistUIState({ active_nav: NAV_EXTRACT });
  }

  async function browseOpen() {
    const path = await open({
      filters: [{ name: "Archives", extensions: ARCHIVE_EXTENSIONS }],
      multiple: false,
    });
    if (typeof path === "string") openCard(path);
  }

  async function doClear() {
    await clearRecents();
    mtimes = {};
  }
</script>

<div class="panel">
  <div class="panel-header glass-raised">
    <div class="header-left">
      <h2 class="panel-title">Recent</h2>
      <span class="count-badge">{paths.length}</span>
    </div>
    <div class="header-actions">
      <button class="btn" onclick={browseOpen}>
        <FolderOpen size={14} />
        Open Archive…
      </button>
      {#if paths.length > 0}
        <button class="btn" onclick={doClear} title="Clear all recent archives">
          <Trash2 size={14} />
          Clear
        </button>
      {/if}
    </div>
  </div>

  <div class="content">
    {#if paths.length === 0}
      <div class="empty-state">
        <div class="empty-icon">
          <Archive size={32} strokeWidth={1.2} />
        </div>
        <p class="empty-title">No recent archives</p>
        <p class="empty-sub">Open an archive to get started</p>
        <button class="btn btn-primary" onclick={browseOpen}>
          <FolderOpen size={14} />
          Browse Files
        </button>
      </div>
    {:else}
      <div class="grid">
        {#each paths as path}
          <button class="card glass-raised" onclick={() => openCard(path)} title={path}>
            <div class="card-icon-wrap">
              <Archive size={24} strokeWidth={1.5} />
              <span class="card-ext">{archiveExt(path)}</span>
            </div>
            <span class="card-name">{archiveName(path)}</span>
            <span class="card-date">
              {mtimes[path] ? relativeTime(mtimes[path]!) : "—"}
            </span>
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .panel { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  /* ── Header ──────────────────────────────────────────────── */

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }

  .header-left { display: flex; align-items: center; gap: 10px; }

  .panel-title { margin: 0; font-size: 18px; font-weight: 600; color: var(--text); }

  .count-badge {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-3);
    background: var(--glass-inset);
    padding: 2px 8px;
    border-radius: 10px;
  }

  .header-actions { display: flex; gap: 8px; }

  /* ── Content area ─────────────────────────────────────────── */

  .content { flex: 1; overflow-y: auto; padding: 20px; }

  /* ── Empty state ─────────────────────────────────────────── */

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    height: 100%;
    min-height: 300px;
    text-align: center;
  }

  .empty-icon {
    width: 64px; height: 64px;
    border-radius: 16px;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-3);
    margin-bottom: 4px;
  }

  .empty-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--text); }
  .empty-sub   { margin: 0; font-size: 13px; color: var(--text-3); }

  /* ── Card grid ───────────────────────────────────────────── */

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
    gap: 12px;
    align-content: start;
  }

  .card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 16px 10px 12px;
    border-radius: 14px;
    cursor: pointer;
    text-align: center;
    transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.15s;
    box-shadow: var(--shadow-sm);
  }

  .card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
  }

  .card:active { transform: translateY(-1px); }

  /* Dark mode: make cards more opaque so text/icons are legible against
     the dark gradient background. The global .glass-raised (0.88) is too
     transparent here — content bleeds through and reduces readability. */
  :global(.dark) .card {
    background-color: rgba(42, 38, 44, 0.96);
  }

  .card-icon-wrap {
    position: relative;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent);
    background: var(--accent-subtle);
    border-radius: 12px;
    border: 1px solid rgba(0, 122, 255, 0.15);
  }

  .card-ext {
    position: absolute;
    bottom: -6px;
    right: -6px;
    font-size: 8px;
    font-weight: 700;
    color: #fff;
    background: var(--accent);
    padding: 1px 4px;
    border-radius: 4px;
    letter-spacing: 0.3px;
  }

  .card-name {
    font-size: 11px;
    font-weight: 500;
    color: var(--text);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-all;
    line-clamp: 2;
    max-width: 100%;
  }

  .card-date { font-size: 10px; color: var(--text-3); margin-top: auto; }
</style>
