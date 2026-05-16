<script lang="ts">
  import { open } from "@tauri-apps/plugin-dialog";
  import { onDestroy, onMount } from "svelte";
  import {
    Archive,
    ChevronDown,
    ChevronRight,
    Download,
    Folder,
    Pencil,
    ShieldCheck,
    X,
  } from "lucide-svelte";
  import {
    cleanupPreview,
    detectEncoding,
    extractArchive,
    extractPreview,
    getArchiveInfo,
    getPreviewServeUrl,
    type InfoResponse,
    listArchive,
    testArchive,
    updateArchive,
  } from "$lib/api/archives";
  import { addRecent } from "$lib/stores/uiState";
  import { appSettings } from "$lib/stores/appSettings";
  import { pendingArchivePath } from "$lib/stores/archive";
  import FileDropZone from "../widgets/FileDropZone.svelte";
  import ArchiveTree from "../widgets/ArchiveTree.svelte";
  import PreviewPane from "../widgets/PreviewPane.svelte";
  import PasswordField from "../widgets/PasswordField.svelte";
  import ProgressBar from "../widgets/ProgressBar.svelte";
  import CollapsibleLog from "../widgets/CollapsibleLog.svelte";
  import PasswordPrompt from "../dialogs/PasswordPrompt.svelte";

  let archivePath: string | null = null;
  let entries: string[] = [];
  let password = "";

  // Password prompt dialog state
  let promptMessage = "";
  let promptResolve: ((v: string | null) => void) | null = null;
  $: showPasswordPrompt = promptResolve !== null;
  let outputDir = $appSettings.default_output_dir;
  let filenameEncoding = $appSettings.default_filename_encoding;
  let passwordEncoding = $appSettings.default_password_encoding;
  let showEncoding = false;
  let working = false;
  let log: string[] = [];
  let progress: number | null = null;
  let editMode = false;

  // Preview state
  let previewEntry: string | null = null;
  let previewTempId: string | null = null;
  let previewFilePath: string | null = null;
  let previewServeUrl: string | null = null;
  let previewLoading = false;
  let archiveInfo: InfoResponse | null = null;

  // ArchiveTree component ref
  let treeComponent: ArchiveTree;

  onMount(() => {
    // Open archive requested from another panel (e.g. Recent)
    return pendingArchivePath.subscribe((path) => {
      if (path) {
        pendingArchivePath.set(null);
        openArchive(path);
      }
    });
  });

  onDestroy(() => {
    if (previewTempId) cleanupPreview(previewTempId).catch(() => {});
  });

  function archiveName(p: string) {
    return p.split(/[\\/]/).pop() ?? p;
  }

  function archiveDir(p: string) {
    const parts = p.split(/[\\/]/);
    parts.pop();
    return parts.join("/") || p;
  }

  async function openArchive(path: string) {
    archivePath = path;
    archiveInfo = null;
    previewEntry = null;
    previewFilePath = null;
    previewServeUrl = null;
    previewTempId = null;
    editMode = false;
    await listEntries(path);
    await addRecent(path);
  }

  async function listEntries(path: string) {
    working = true;
    log = [];
    try {
      const result = await listArchive({
        archive_path: path,
        password: password || undefined,
        filename_encoding: filenameEncoding || null,
        password_encoding: passwordEncoding || null,
      });
      if (result.ok) {
        entries = result.names;
        // Apply encoding from list result or auto-detect if unknown
        if (result.encoding && result.encoding !== filenameEncoding) {
          filenameEncoding = result.encoding;
          log = [`Auto-detected encoding: ${result.encoding}`];
        } else if (!filenameEncoding) {
          const detected = await detectEncoding({ archive_path: path }).catch(() => null);
          if (detected?.encoding && detected.confidence > 0.7) {
            filenameEncoding = detected.encoding;
            log = [
              `Auto-detected encoding: ${detected.encoding} (${Math.round(detected.confidence * 100)}%)`,
            ];
          }
        }
        // Fetch archive metadata for the Info panel
        getArchiveInfo({ archive_path: path, password: password || undefined })
          .then((info) => {
            archiveInfo = info;
          })
          .catch(() => {});
      } else {
        const pwd = await promptPassword("Archive is password-protected. Enter password:");
        if (pwd !== null) {
          password = pwd;
          await listEntries(path);
        } else {
          closeArchive();
        }
      }
    } catch (e) {
      log = [`✗ ${e}`];
    } finally {
      working = false;
    }
  }

  function closeArchive() {
    archivePath = null;
    entries = [];
    previewEntry = null;
    previewFilePath = null;
    previewServeUrl = null;
    if (previewTempId) {
      cleanupPreview(previewTempId).catch(() => {});
      previewTempId = null;
    }
    archiveInfo = null;
    log = [];
    editMode = false;
  }

  async function doTest() {
    if (!archivePath) return;
    working = true;
    log = ["Testing archive integrity…"];
    try {
      const result = await testArchive({
        archive_path: archivePath,
        password: password || undefined,
        filename_encoding: filenameEncoding || null,
        password_encoding: passwordEncoding || null,
      });
      log = result.ok
        ? ["✓ Archive integrity OK."]
        : [`✗ Failed entries: ${result.failed.join(", ")}`];
    } catch (e) {
      log = [`✗ ${e}`];
    } finally {
      working = false;
    }
  }

  async function doExtract() {
    if (!archivePath) return;
    working = true;
    progress = null;
    log = ["Starting extraction…"];
    await extractArchive(
      {
        archive_path: archivePath,
        password: password || undefined,
        output_dir: outputDir || null,
        filename_encoding: filenameEncoding || null,
        password_encoding: passwordEncoding || null,
        smart: $appSettings.smart_extraction,
      },
      {
        progress: (d: any) => {
          progress = d.total > 0 ? d.current / d.total : null;
        },
        bytes_progress: () => {},
        log: (d: any) => {
          log = [...log, d.message];
        },
        complete: (d: any) => {
          log = [...log, d.ok ? "✓ Extraction complete." : "✗ Extraction failed."];
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

  async function onEntrySelected(e: CustomEvent<string>) {
    const entry = e.detail;
    if (!archivePath || !entry || entry.endsWith("/")) return;
    previewEntry = entry;

    // Clean up previous preview
    if (previewTempId) {
      cleanupPreview(previewTempId).catch(() => {});
      previewTempId = null;
      previewFilePath = null;
      previewServeUrl = null;
    }

    previewLoading = true;
    try {
      const result = await extractPreview({
        archive_path: archivePath,
        entry_name: entry,
        password: password || undefined,
        filename_encoding: filenameEncoding || null,
        password_encoding: passwordEncoding || null,
      });
      previewTempId = result.temp_id;
      previewFilePath = result.file_path;
      previewServeUrl = await getPreviewServeUrl(result.file_path);
    } catch {
      previewFilePath = null;
      previewServeUrl = null;
    } finally {
      previewLoading = false;
    }
  }

  async function onEntriesModified(e: CustomEvent<{ add: string[]; remove: string[] }>) {
    if (!archivePath) return;
    working = true;
    log = ["Updating archive…"];
    try {
      const result = await updateArchive({
        archive_path: archivePath,
        files_to_add: e.detail.add,
        paths_to_remove: e.detail.remove,
      });
      log = [result.ok ? "✓ Archive updated." : "✗ Update failed."];
      if (result.ok) await listEntries(archivePath);
    } catch (err) {
      log = [`✗ ${err}`];
    } finally {
      working = false;
      editMode = false;
    }
  }

  async function browseOutputDir() {
    const dir = await open({ directory: true, multiple: false });
    if (typeof dir === "string") outputDir = dir;
  }

  async function detectFileEncoding() {
    if (!archivePath) return;
    const result = await detectEncoding({ archive_path: archivePath }).catch(() => null);
    if (result?.encoding) {
      filenameEncoding = result.encoding;
      log = [
        `Detected encoding: ${result.encoding} (confidence: ${Math.round(result.confidence * 100)}%)`,
      ];
    }
  }

  async function promptPassword(message: string): Promise<string | null> {
    return new Promise((resolve) => {
      promptMessage = message;
      promptResolve = resolve;
    });
  }

  function onPromptSubmit(pwd: string) {
    const r = promptResolve;
    promptResolve = null;
    r?.(pwd);
  }

  function onPromptCancel() {
    const r = promptResolve;
    promptResolve = null;
    r?.(null);
  }
</script>

<div class="panel">
  <ProgressBar active={working} {progress} />

  {#if !archivePath}
    <FileDropZone on:path={(e) => openArchive(e.detail)} />
  {:else}
    <!-- Archive bar -->
    <div class="archive-bar">
      <span class="arch-icon"><Archive size={18} strokeWidth={1.5} /></span>
      <div class="arch-info">
        <span class="arch-name">{archiveName(archivePath)}</span>
        <span class="arch-dir">{archiveDir(archivePath)}</span>
      </div>
      <button class="close-btn" onclick={closeArchive} title="Close archive">
        <X size={14} />
      </button>
    </div>

    <!-- Tree + Preview -->
    <div class="main-split">
      <div class="left-pane">
        <ArchiveTree
          bind:this={treeComponent}
          names={entries}
          {editMode}
          on:entrySelected={onEntrySelected}
          on:entriesModified={onEntriesModified}
        />

        <!-- Edit mode action buttons -->
        {#if editMode}
          <div class="edit-actions">
            <button class="btn" onclick={() => treeComponent?.saveEdits()}>Save</button>
            <button
              class="btn"
              onclick={() => {
                editMode = false;
                treeComponent?.cancelEdits();
              }}
              >Cancel
            </button>
          </div>
        {/if}
      </div>

      <PreviewPane
        entryPath={previewEntry}
        filePath={previewFilePath}
        serveUrl={previewServeUrl}
        {archiveInfo}
        loading={previewLoading}
      />
    </div>

    <!-- Bottom strip -->
    <div class="bottom-strip">
      <PasswordField bind:value={password} placeholder="Password" disabled={working} />

      <div class="output-row">
        <input
          class="input"
          bind:value={outputDir}
          placeholder="Output directory (default: smart)"
          readonly
        />
        <button class="btn" onclick={browseOutputDir} title="Browse">
          <Folder size={13} />
        </button>
      </div>

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
          <button class="btn" onclick={detectFileEncoding}>Detect</button>
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

      <div class="actions-row">
        <button class="btn encoding-toggle" onclick={() => (showEncoding = !showEncoding)}>
          {#if showEncoding}
            <ChevronDown size={12} />
          {:else}
            <ChevronRight size={12} />
          {/if}
          Encoding
        </button>
        <div style="flex:1"></div>
        <button class="btn" onclick={doTest} disabled={working}>
          <ShieldCheck size={13} />
          Test
        </button>
        {#if !editMode}
          <button class="btn" onclick={() => (editMode = true)} disabled={working}>
            <Pencil size={13} />
            Edit
          </button>
          <button
            class="btn btn-primary"
            onclick={doExtract}
            disabled={working || entries.length === 0}
          >
            <Download size={13} />
            Extract
          </button>
        {/if}
      </div>
    </div>
  {/if}

  <CollapsibleLog {log} />
</div>

{#if showPasswordPrompt}
  <PasswordPrompt message={promptMessage} onSubmit={onPromptSubmit} onCancel={onPromptCancel} />
{/if}

<style>
  .panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  /* ── Archive bar ──────────────────────────────────────────── */

  .archive-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--glass-border);
    background: var(--glass-raised);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    flex-shrink: 0;
  }

  .arch-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: var(--accent-subtle);
    color: var(--accent);
    flex-shrink: 0;
  }

  .arch-info {
    flex: 1;
    overflow: hidden;
  }

  .arch-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .arch-dir {
    font-size: 11px;
    color: var(--text-3);
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-top: 1px;
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
    transition:
      background 0.12s,
      color 0.12s;
  }

  .close-btn:hover {
    background: var(--error-subtle);
    color: var(--error);
  }

  /* ── Main split ───────────────────────────────────────────── */

  .main-split {
    display: flex;
    flex: 1;
    overflow: hidden;
    min-height: 0;
    gap: 0;
  }

  .left-pane {
    display: flex;
    flex-direction: column;
    width: 55%;
    min-width: 200px;
    border-right: 1px solid var(--glass-border);
    overflow: hidden;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
  }

  /* ── Edit mode actions ────────────────────────────────────── */

  .edit-actions {
    display: flex;
    gap: 6px;
    padding: 8px 10px;
    border-top: 1px solid var(--glass-border);
    background: var(--warning-subtle);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
  }

  /* ── Bottom strip ─────────────────────────────────────────── */

  .bottom-strip {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 14px;
    border-top: 1px solid var(--glass-border);
    background: var(--glass-raised);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    flex-shrink: 0;
  }

  .output-row,
  .encoding-row {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .output-row .input,
  .encoding-row .input {
    flex: 1;
  }

  .enc-label {
    font-size: 11px;
    color: var(--text-3);
    width: 60px;
    flex-shrink: 0;
  }

  .actions-row {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }

  .encoding-toggle {
    color: var(--text-2);
  }
</style>
