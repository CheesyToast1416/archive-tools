<script lang="ts">
  import { getVersion } from "@tauri-apps/api/app";
  import { Settings, X } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { appSettings, persistAppSettings } from "$lib/stores/appSettings";

  let { close } = $props();

  let draft = { ...$appSettings };
  let version = $state("");
  onMount(async () => {
    version = await getVersion();
  });

  async function save() {
    await persistAppSettings(draft);
    close();
  }
</script>

<div class="overlay">
  <div class="dialog glass-raised">
    <div class="dialog-header">
      <div class="header-icon">
        <Settings size={16} color="var(--accent)" />
      </div>
      <span class="dialog-title">Preferences</span>
      <button class="close-btn" onclick={() => close()}>
        <X size={14} />
      </button>
    </div>

    <div class="dialog-body">
      <section>
        <div class="section-label">Extraction</div>
        <div class="setting-group">
          <label class="setting-row">
            <div class="setting-info">
              <span class="setting-name">Smart extraction</span>
              <span class="setting-desc">Auto-detect archive structure for clean output</span>
            </div>
            <input type="checkbox" class="toggle" bind:checked={draft.smart_extraction} />
          </label>
          <label class="setting-row">
            <div class="setting-info">
              <span class="setting-name">Trash archive after extraction</span>
              <span class="setting-desc">Move the archive to trash when done</span>
            </div>
            <input type="checkbox" class="toggle" bind:checked={draft.trash_after_extract} />
          </label>
          <div class="setting-row field-row">
            <div class="setting-info">
              <span class="setting-name">Default output directory</span>
            </div>
            <input
              class="input field-input"
              bind:value={draft.default_output_dir}
              placeholder="Same as archive"
            />
          </div>
        </div>
      </section>

      <section>
        <div class="section-label">Archive Creation</div>
        <div class="setting-group">
          <label class="setting-row">
            <div class="setting-info">
              <span class="setting-name">Trash sources after creation</span>
            </div>
            <input type="checkbox" class="toggle" bind:checked={draft.trash_after_create} />
          </label>
          <label class="setting-row">
            <div class="setting-info">
              <span class="setting-name">Trash archives after batch extraction</span>
            </div>
            <input type="checkbox" class="toggle" bind:checked={draft.trash_after_batch} />
          </label>
        </div>
      </section>

      <section>
        <div class="section-label">Encoding Defaults</div>
        <div class="setting-group">
          <div class="setting-row field-row">
            <div class="setting-info">
              <span class="setting-name">Filename encoding</span>
            </div>
            <select class="input field-input" bind:value={draft.default_filename_encoding}>
              <option value="">Auto-detect</option>
              <option value="utf-8">UTF-8</option>
              <option value="gbk">GBK</option>
              <option value="gb18030">GB18030</option>
              <option value="shift_jis">Shift-JIS</option>
              <option value="euc-kr">EUC-KR</option>
              <option value="cp437">CP437</option>
            </select>
          </div>
          <div class="setting-row field-row">
            <div class="setting-info">
              <span class="setting-name">Password encoding</span>
            </div>
            <select class="input field-input" bind:value={draft.default_password_encoding}>
              <option value="">UTF-8 (default)</option>
              <option value="gbk">GBK</option>
              <option value="shift_jis">Shift-JIS</option>
            </select>
          </div>
        </div>
      </section>

      <section>
        <div class="section-label">Notifications</div>
        <div class="setting-group">
          <label class="setting-row">
            <div class="setting-info">
              <span class="setting-name">Desktop notifications</span>
              <span class="setting-desc">Show a notification when operations complete</span>
            </div>
            <input type="checkbox" class="toggle" bind:checked={draft.notifications_enabled} />
          </label>
        </div>
      </section>
    </div>

    <div class="dialog-footer">
      <span class="version-tag">v{version}</span>
      <button class="btn" onclick={() => close()}>Cancel</button>
      <button class="btn btn-primary" onclick={save}>Save Changes</button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .dialog {
    width: 480px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    border-radius: 16px;
    box-shadow: var(--shadow-xl);
    overflow: hidden;
  }

  /* ── Header ─────────────────────────────────────────────── */

  .dialog-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px 12px;
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }

  .header-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: var(--accent-subtle);
    flex-shrink: 0;
  }

  .dialog-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    flex: 1;
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
    transition:
      background 0.12s,
      color 0.12s;
  }

  .close-btn:hover {
    background: var(--glass-inset);
    color: var(--text);
  }

  /* ── Body ───────────────────────────────────────────────── */

  .dialog-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .setting-group {
    display: flex;
    flex-direction: column;
    gap: 1px;
    background: var(--glass-border);
    border-radius: 10px;
    overflow: hidden;
  }

  .setting-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 12px;
    background: var(--glass-inset);
    cursor: pointer;
    transition: background 0.1s;
  }

  .setting-row:hover {
    background: var(--glass);
  }

  .setting-row.field-row {
    cursor: default;
  }

  .setting-row.field-row:hover {
    background: var(--glass-inset);
  }

  .setting-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
  }

  .setting-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
  }

  .setting-desc {
    font-size: 11px;
    color: var(--text-3);
  }

  /* Toggle switch */
  .toggle {
    width: 36px;
    height: 20px;
    appearance: none;
    border-radius: 10px;
    background: var(--glass-border);
    position: relative;
    cursor: pointer;
    transition: background 0.2s;
    flex-shrink: 0;
  }

  .toggle::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #fff;
    transition: transform 0.2s;
    box-shadow: var(--shadow-sm);
  }

  .toggle:checked {
    background: var(--accent);
  }

  .toggle:checked::after {
    transform: translateX(16px);
  }

  .field-input {
    max-width: 200px;
  }

  /* ── Footer ─────────────────────────────────────────────── */

  .dialog-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--glass-border);
    flex-shrink: 0;
  }

  .version-tag {
    font-size: 11px;
    color: var(--text-3);
    flex: 1;
  }
</style>
