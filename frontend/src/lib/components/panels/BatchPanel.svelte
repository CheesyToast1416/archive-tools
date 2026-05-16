<script lang="ts">
  import { open } from "@tauri-apps/plugin-dialog";
  import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
  import { onDestroy, onMount } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { batchExtract } from "$lib/api/archives";
  import { appSettings } from "$lib/stores/appSettings";
  import { ChevronDown, ChevronRight } from "@lucide/svelte";
  import PasswordField from "../widgets/PasswordField.svelte";
  import ProgressBar from "../widgets/ProgressBar.svelte";
  import CollapsibleLog from "../widgets/CollapsibleLog.svelte";
  import { ARCHIVE_EXTENSIONS } from "$lib/constants";

  interface ArchiveRow {
    path: string;
    status: "pending" | "working" | "done" | "failed";
    detail: string;
  }

  let rows: ArchiveRow[] = [];
  let selected = new SvelteSet<number>();
  let password = "";
  let outputDir = $appSettings.default_output_dir;
  let filenameEncoding = $appSettings.default_filename_encoding;
  let passwordEncoding = $appSettings.default_password_encoding;
  let trashAfterBatch = $appSettings.trash_after_batch;
  let showEncoding = false;
  let working = false;
  let log: string[] = [];
  let progress: number | null = null;
  let unlisten: (() => void) | null = null;

  onMount(async () => {
    const win = getCurrentWebviewWindow();
    unlisten = await win.onDragDropEvent((event) => {
      if (event.payload.type === "drop") {
        const paths: string[] = (event.payload as any).paths ?? [];
        addPaths(paths);
      }
    });
  });

  onDestroy(() => unlisten?.());

  function archiveName(p: string) {
    return p.split(/[\\/]/).pop() ?? p;
  }

  function addPaths(paths: string[]) {
    const newOnes = paths.filter((p) => !rows.find((r) => r.path === p));
    rows = [...rows, ...newOnes.map((p) => ({ path: p, status: "pending" as const, detail: "" }))];
  }

  async function addArchives() {
    const paths = await open({
      multiple: true,
      filters: [{ name: "Archives", extensions: ARCHIVE_EXTENSIONS }],
    });
    if (Array.isArray(paths)) addPaths(paths);
  }

  function toggleSelect(i: number) {
    if (selected.has(i)) selected.delete(i);
    else selected.add(i);
    selected = selected;
  }

  function removeSelected() {
    rows = rows.filter((_, i) => !selected.has(i));
    selected = new SvelteSet();
  }

  async function doExtractAll() {
    if (rows.length === 0) return;
    working = true;
    selected = new SvelteSet();
    log = [];
    rows = rows.map((r) => ({ ...r, status: "pending", detail: "" }));

    await batchExtract(
      {
        archives: rows.map((r) => r.path),
        output_dir: outputDir || null,
        password,
        filename_encoding: filenameEncoding || null,
        password_encoding: passwordEncoding || null,
      },
      {
        archive_started: (d: any) => {
          rows[d.index] = { ...rows[d.index], status: "working" };
          rows = rows;
        },
        archive_done: (d: any) => {
          rows[d.index] = {
            ...rows[d.index],
            status: d.ok ? "done" : "failed",
            detail: d.detail ?? "",
          };
          rows = rows;
        },
        file_progress: (d: any) => {
          progress = d.total > 0 ? d.current / d.total : null;
        },
        bytes_progress: () => {},
        log: (d: any) => {
          log = [...log, d.message];
        },
        complete: (d: any) => {
          log = [...log, `✓ Done — ${d.ok_count} succeeded, ${d.fail_count} failed.`];
        },
        error: (d: any) => {
          log = [...log, `✗ ${d.message}`];
        },
      }
    ).finally(() => {
      working = false;
      progress = null;
    });
  }
</script>

<div class="panel">
  <ProgressBar active={working} {progress} />

  <div class="toolbar">
    <button class="btn" onclick={addArchives} disabled={working}>Add Archives</button>
    <button class="btn" onclick={removeSelected} disabled={working || selected.size === 0}>
      Remove ({selected.size})
    </button>
    <button
      class="btn"
      onclick={() => {
        rows = [];
        selected = new SvelteSet();
      }}
      disabled={working}
      >Clear
    </button>
    <span class="counter">{rows.filter((r) => r.status === "done").length} / {rows.length}</span>
    <button
      class="btn btn-primary"
      style="margin-left:auto"
      onclick={doExtractAll}
      disabled={working || rows.length === 0}
    >
      {working ? "Extracting…" : "Extract All"}
    </button>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="col-check"></th>
          <th>Archive</th>
          <th>Status</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row, i (i)}
          <tr class:working={row.status === "working"} class:selected={selected.has(i)}>
            <td class="col-check">
              <input
                type="checkbox"
                checked={selected.has(i)}
                onchange={() => toggleSelect(i)}
                disabled={working}
              />
            </td>
            <td title={row.path}>{archiveName(row.path)}</td>
            <td class="status {row.status}">
              {row.status === "pending"
                ? "Pending"
                : row.status === "working"
                  ? "Extracting…"
                  : row.status === "done"
                    ? "✓ Done"
                    : "✗ Failed"}
            </td>
            <td class="detail">{row.detail}</td>
          </tr>
        {/each}
        {#if rows.length === 0}
          <tr>
            <td colspan="4" class="empty-row">No archives — drag files here or use Add Archives</td>
          </tr>
        {/if}
      </tbody>
    </table>
  </div>

  <div class="options">
    <div class="section-label">SHARED OPTIONS</div>
    <PasswordField bind:value={password} placeholder="Shared password" />
    <input
      class="input"
      bind:value={outputDir}
      placeholder="Output directory (blank = next to each archive)"
    />
    <label class="checkbox-label">
      <input type="checkbox" bind:checked={trashAfterBatch} />
      Trash archives after extraction
    </label>
    <button class="btn encoding-toggle" onclick={() => (showEncoding = !showEncoding)}>
      {#if showEncoding}
        <ChevronDown size={12} />
      {:else}
        <ChevronRight size={12} />
      {/if}
      Encoding
    </button>
    {#if showEncoding}
      <div class="encoding-row">
        <span class="enc-label">Filenames</span>
        <select class="input" bind:value={filenameEncoding}>
          <option value="">Auto-detect</option>
          <option value="utf-8">UTF-8</option>
          <option value="gbk">GBK</option>
          <option value="gb18030">GB18030</option>
          <option value="shift_jis">Shift-JIS</option>
          <option value="euc-kr">EUC-KR</option>
          <option value="cp437">CP437</option>
        </select>
      </div>
      <div class="encoding-row">
        <span class="enc-label">Passwords</span>
        <select class="input" bind:value={passwordEncoding}>
          <option value="">UTF-8 (default)</option>
          <option value="gbk">GBK</option>
          <option value="shift_jis">Shift-JIS</option>
        </select>
      </div>
    {/if}
  </div>

  <CollapsibleLog {log} />
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    height: 100%;
    overflow: hidden;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
  }

  .toolbar {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }

  .counter {
    font-size: 12px;
    color: var(--text-3);
  }

  .table-wrap {
    flex: 1;
    overflow-y: auto;
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    background: var(--glass-inset);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  thead th {
    background: var(--glass-raised);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    padding: 7px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    color: var(--text-2);
    position: sticky;
    top: 0;
    border-bottom: 1px solid var(--glass-border);
  }

  tbody td {
    padding: 6px 10px;
    border-top: 1px solid var(--glass-border);
  }

  tr.working {
    background: var(--accent-subtle);
  }

  tr.selected {
    background: color-mix(in srgb, var(--accent) 8%, transparent);
  }

  .col-check {
    width: 32px;
    text-align: center;
  }

  .status.done {
    color: var(--success);
    font-weight: 500;
  }

  .status.failed {
    color: var(--error);
    font-weight: 500;
  }

  .status.working {
    color: var(--accent);
    font-weight: 500;
  }

  .detail {
    color: var(--text-3);
    font-size: 11px;
  }

  .empty-row {
    text-align: center;
    color: var(--text-3);
    padding: 24px 8px !important;
  }

  .options {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-2);
    cursor: pointer;
  }

  .encoding-toggle {
    color: var(--text-2);
    align-self: flex-start;
  }

  .encoding-row {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .encoding-row .input {
    flex: 1;
  }

  .enc-label {
    font-size: 11px;
    color: var(--text-3);
    width: 60px;
    flex-shrink: 0;
  }
</style>
