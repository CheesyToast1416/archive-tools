<script lang="ts">
  import { onMount } from "svelte";
  import { listen } from "@tauri-apps/api/event";
  import { check as checkUpdate, type Update } from "@tauri-apps/plugin-updater";
  import "../app.css";
  import { loadUIState, uiState } from "$lib/stores/uiState";
  import { loadAppSettings } from "$lib/stores/appSettings";
  import Sidebar from "../lib/components/Sidebar.svelte";
  import { NAV_BATCH, NAV_CONVERT, NAV_CREATE, NAV_EXTRACT, NAV_RECENT } from "$lib/constants";
  import { Sparkles, TriangleAlert, X } from "@lucide/svelte";

  import ExtractPanel from "../lib/components/panels/ExtractPanel.svelte";
  import RecentPanel from "../lib/components/panels/RecentPanel.svelte";
  import CreatePanel from "../lib/components/panels/CreatePanel.svelte";
  import BatchPanel from "../lib/components/panels/BatchPanel.svelte";
  import ConvertPanel from "../lib/components/panels/ConvertPanel.svelte";

  let ready = false;
  let error: string | null = null;
  let sidecarDown = false;
  let updateAvailable: string | null = null;
  let installingUpdate = false;
  let updateObj: Update | null = null;

  onMount(async () => {
    try {
      await Promise.all([loadUIState(), loadAppSettings()]);
      ready = true;
    } catch (e) {
      error = String(e);
      return;
    }

    await listen("sidecar-unavailable", () => {
      sidecarDown = true;
    });

    checkUpdate()
      .then((update: Update | null) => {
        if (update?.available) {
          updateAvailable = update.currentVersion ?? "new version";
          updateObj = update;
        }
      })
      .catch(() => {});
  });

  async function installUpdate() {
    if (!updateObj) return;
    installingUpdate = true;
    try {
      await updateObj.downloadAndInstall();
    } catch {
      installingUpdate = false;
      updateAvailable = null;
    }
  }
</script>

{#if error}
  <div class="splash">
    <div class="splash-card glass-raised">
      <TriangleAlert size={32} color="var(--error)" />
      <h2>Could not connect to server</h2>
      <p>{error}</p>
    </div>
  </div>
{:else if !ready}
  <div class="splash">
    <div class="splash-card glass-raised">
      <div class="spinner"></div>
      <p>Starting…</p>
    </div>
  </div>
{:else}
  <div class="app-root">
    <Sidebar />
    <main class="content">
      {#if sidecarDown}
        <div class="banner banner-error">
          <TriangleAlert size={14} />
          The ArchiveTools backend has stopped responding. Please restart the app.
        </div>
      {/if}
      {#if updateAvailable}
        <div class="banner banner-info">
          <Sparkles size={14} />
          Version {updateAvailable} is available.
          <button class="btn-link" onclick={installUpdate} disabled={installingUpdate}>
            {installingUpdate ? "Installing…" : "Install and restart"}
          </button>
          <button class="btn-dismiss" onclick={() => (updateAvailable = null)}>
            <X size={13} />
          </button>
        </div>
      {/if}

      {#if $uiState.active_nav === NAV_RECENT}
        <RecentPanel />
      {:else if $uiState.active_nav === NAV_EXTRACT}
        <ExtractPanel />
      {:else if $uiState.active_nav === NAV_CREATE}
        <CreatePanel />
      {:else if $uiState.active_nav === NAV_BATCH}
        <BatchPanel />
      {:else if $uiState.active_nav === NAV_CONVERT}
        <ConvertPanel />
      {/if}
    </main>
  </div>
{/if}

<style>
  .app-root {
    display: flex;
    height: 100vh;
    overflow: hidden;
    background: var(--bg);
    background-attachment: fixed;
  }

  .content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  /* ── Splash screens ─────────────────────────────────────────── */

  .splash {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    background: var(--bg);
    background-attachment: fixed;
  }

  .splash-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 32px 40px;
    border-radius: 16px;
    box-shadow: var(--shadow-xl);
    text-align: center;
    min-width: 260px;
  }

  .splash-card h2 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
  }

  .splash-card p {
    margin: 0;
    font-size: 12px;
    color: var(--text-2);
    max-width: 240px;
  }

  .spinner {
    width: 24px;
    height: 24px;
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

  /* ── Notification banners ───────────────────────────────────── */

  .banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 500;
    flex-shrink: 0;
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
  }

  .banner-error {
    background: var(--error-subtle);
    color: var(--error);
    border-bottom: 1px solid rgba(255, 69, 58, 0.2);
  }

  .banner-info {
    background: var(--accent-subtle);
    color: var(--text);
    border-bottom: 1px solid var(--glass-border);
  }

  .btn-link {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    text-decoration: underline;
    font-size: 12px;
    font-family: var(--font-sans), sans-serif;
    padding: 0;
  }

  .btn-link:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .btn-dismiss {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-3);
    cursor: pointer;
    display: flex;
    align-items: center;
    padding: 2px;
    border-radius: 4px;
    transition: color 0.12s;
  }

  .btn-dismiss:hover {
    color: var(--text);
  }
</style>
