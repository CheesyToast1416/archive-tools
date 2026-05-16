<script lang="ts">
  import { open, save } from "@tauri-apps/plugin-dialog";
  import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
  import { onDestroy, onMount } from "svelte";
  import { ARCHIVE_FORMATS } from "$lib/constants";
  import { createArchive } from "$lib/api/archives";
  import { appSettings } from "$lib/stores/appSettings";
  import PasswordField from "../widgets/PasswordField.svelte";
  import CollapsibleLog from "../widgets/CollapsibleLog.svelte";

  let files: string[] = [];
  let outputPath = "";
  let format = "zip";
  let compression = 6;
  let password = "";
  let trashAfterCreate = $appSettings.trash_after_create;
  let log: string[] = [];
  let working = false;
  let unlisten: (() => void) | null = null;

  $: selectedFormat = ARCHIVE_FORMATS.find((f) => f.key === format);
  $: showPassword = selectedFormat?.supportsPassword ?? false;
  $: showCompression = !format.startsWith("tar");

  onMount(async () => {
    const win = getCurrentWebviewWindow();
    unlisten = await win.onDragDropEvent((event) => {
      if (event.payload.type === "drop") {
        const paths: string[] = (event.payload as any).paths ?? [];
        const newOnes = paths.filter((p) => !files.includes(p));
        if (newOnes.length) files = [...files, ...newOnes];
      }
    });
  });

  onDestroy(() => unlisten?.());

  async function browseFiles() {
    const paths = await open({ multiple: true });
    if (Array.isArray(paths)) {
      files = [...new Set([...files, ...paths])];
    }
  }

  async function browseOutput() {
    const fmt = ARCHIVE_FORMATS.find((f) => f.key === format);
    const path = await save({
      filters: [{ name: "Archive", extensions: [(fmt?.ext ?? ".zip").replace(".", "")] }],
    });
    if (path) outputPath = path;
  }

  function removeFile(idx: number) {
    files = files.filter((_, i) => i !== idx);
  }

  async function doCreate() {
    if (!outputPath || files.length === 0) return;
    working = true;
    log = [];
    try {
      const result = await createArchive({
        output_path: outputPath,
        files,
        format,
        password: showPassword && password ? password : null,
        compression_level: compression,
      });
      log = [result.ok ? "✓ Archive created successfully." : "✗ Archive creation failed."];
    } catch (e) {
      log = [`✗ Error: ${e}`];
    } finally {
      working = false;
    }
  }
</script>

<div class="panel">
  <div class="section-label">OUTPUT</div>
  <div class="row">
    <input class="input" bind:value={outputPath} placeholder="Output archive path…" readonly />
    <button class="btn" onclick={browseOutput}>…</button>
  </div>

  <div class="section-label">FILES</div>
  <div class="file-list" role="list">
    {#each files as f, i (f)}
      <div class="file-row" role="listitem">
        <span class="file-name" title={f}>{f.split(/[\\/]/).pop()}</span>
        <button class="remove-btn" onclick={() => removeFile(i)}>✕</button>
      </div>
    {/each}
    {#if files.length === 0}
      <div class="empty-list">Drag files here or use Add Files</div>
    {/if}
  </div>
  <div class="row">
    <button class="btn" onclick={browseFiles}>Add Files</button>
    <button class="btn" onclick={() => (files = [])}>Clear</button>
  </div>

  <div class="section-label">OPTIONS</div>
  <div class="options-row">
    <select class="input" bind:value={format}>
      {#each ARCHIVE_FORMATS as fmt (fmt.key)}
        <option value={fmt.key}>{fmt.label}</option>
      {/each}
    </select>
    {#if showCompression}
      <div class="compression-row">
        <span>Compression: {compression}</span>
        <input type="range" min="0" max="9" bind:value={compression} />
      </div>
    {/if}
  </div>
  {#if showPassword}
    <PasswordField bind:value={password} placeholder="Archive password" />
  {/if}

  <div class="action-row">
    <label class="checkbox-label">
      <input type="checkbox" bind:checked={trashAfterCreate} />
      Move sources to trash after creation
    </label>
    <button
      class="btn btn-primary"
      onclick={doCreate}
      disabled={working || !outputPath || files.length === 0}
    >
      {working ? "Creating…" : "Create Archive"}
    </button>
  </div>

  <CollapsibleLog {log} />
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 20px;
    height: 100%;
    overflow-y: auto;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
  }

  .row {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .file-list {
    min-height: 80px;
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    background: var(--glass-inset);
  }

  .file-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border-bottom: 1px solid var(--glass-border);
    transition: background 0.1s;
  }

  .file-row:last-child {
    border-bottom: none;
  }

  .file-row:hover {
    background: var(--glass-raised);
  }

  .file-name {
    font-size: 12px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .remove-btn {
    display: flex;
    align-items: center;
    background: none;
    border: none;
    color: var(--text-3);
    cursor: pointer;
    padding: 2px;
    border-radius: 4px;
    transition: color 0.12s;
    flex-shrink: 0;
  }

  .remove-btn:hover {
    color: var(--error);
  }

  .empty-list {
    color: var(--text-3);
    font-size: 12px;
    text-align: center;
    padding: 24px 20px;
  }

  .options-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .compression-row {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    color: var(--text-2);
  }

  .compression-row input[type="range"] {
    flex: 1;
    accent-color: var(--accent);
  }

  .action-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 4px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-2);
    cursor: pointer;
  }
</style>
