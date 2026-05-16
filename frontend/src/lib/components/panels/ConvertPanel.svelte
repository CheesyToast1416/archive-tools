<script lang="ts">
  import { open, save } from "@tauri-apps/plugin-dialog";
  import { ChevronDown, ChevronRight } from "@lucide/svelte";
  import { ARCHIVE_EXTENSIONS, ARCHIVE_FORMATS } from "$lib/constants";
  import { convertArchive } from "$lib/api/archives";
  import { appSettings } from "$lib/stores/appSettings";
  import PasswordField from "../widgets/PasswordField.svelte";
  import CollapsibleLog from "../widgets/CollapsibleLog.svelte";

  let sourcePath = "";
  let sourcePassword = "";
  let outputFormat = "zip";
  let outputPath = "";
  let outputPassword = "";
  let filenameEncoding = $appSettings.default_filename_encoding;
  let passwordEncoding = $appSettings.default_password_encoding;
  let showEncoding = false;
  let working = false;
  let log: string[] = [];

  $: selectedFmt = ARCHIVE_FORMATS.find((f) => f.key === outputFormat);
  $: showOutputPassword = selectedFmt?.supportsPassword ?? false;

  async function browseSource() {
    const path = await open({
      filters: [{ name: "Archives", extensions: ARCHIVE_EXTENSIONS }],
      multiple: false,
    });
    if (typeof path === "string") sourcePath = path;
  }

  async function browseOutput() {
    const ext = (selectedFmt?.ext ?? ".zip").replace(".", "");
    const path = await save({ filters: [{ name: "Archive", extensions: [ext] }] });
    if (path) outputPath = path;
  }

  async function doConvert() {
    if (!sourcePath || !outputPath) return;
    working = true;
    log = [];
    try {
      const result = await convertArchive({
        input_path: sourcePath,
        output_path: outputPath,
        output_format: outputFormat,
        password: sourcePassword || null,
        output_password: showOutputPassword && outputPassword ? outputPassword : null,
        filename_encoding: filenameEncoding || null,
        password_encoding: passwordEncoding || null,
      });
      log = [result.ok ? "✓ Conversion complete." : "✗ Conversion failed."];
    } catch (e) {
      log = [`✗ Error: ${e}`];
    } finally {
      working = false;
    }
  }
</script>

<div class="panel">
  <div class="section-label">SOURCE ARCHIVE</div>
  <div class="row">
    <input class="input" bind:value={sourcePath} placeholder="Source archive path…" readonly />
    <button class="btn" onclick={browseSource}>…</button>
  </div>
  <PasswordField bind:value={sourcePassword} placeholder="Source password" />

  <div class="section-label">OUTPUT ARCHIVE</div>
  <select class="input" bind:value={outputFormat}>
    {#each ARCHIVE_FORMATS as fmt (fmt.key)}
      <option value={fmt.key}>{fmt.label}</option>
    {/each}
  </select>
  <div class="row">
    <input class="input" bind:value={outputPath} placeholder="Output path…" readonly />
    <button class="btn" onclick={browseOutput}>…</button>
  </div>
  {#if showOutputPassword}
    <PasswordField bind:value={outputPassword} placeholder="Output password" />
  {/if}

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

  <button
    class="btn btn-primary"
    style="margin-top: 8px; align-self: flex-end"
    onclick={doConvert}
    disabled={working || !sourcePath || !outputPath}
  >
    {working ? "Converting…" : "Convert Archive"}
  </button>

  <CollapsibleLog {log} />
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
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

  .encoding-toggle {
    color: var(--text-2);
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
