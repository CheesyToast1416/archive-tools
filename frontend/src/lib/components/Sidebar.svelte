<script lang="ts">
  import {
    Archive,
    ArrowLeftRight,
    Clock,
    KeyRound,
    Layers,
    Moon,
    PackageOpen,
    PackagePlus,
    Settings,
    Sun,
  } from "lucide-svelte";
  import { uiState, persistUIState, applyTheme } from "../stores/uiState";
  import { NAV_BATCH, NAV_CONVERT, NAV_CREATE, NAV_EXTRACT, NAV_RECENT } from "../constants";
  import SettingsDialog from "./dialogs/SettingsDialog.svelte";
  import PasswordManager from "./dialogs/PasswordManager.svelte";

  let showSettings = false;
  let showPasswords = false;

  const navItems = [
    { idx: NAV_RECENT,  label: "Recent",  Icon: Clock        },
    { idx: NAV_EXTRACT, label: "Extract", Icon: PackageOpen   },
    { idx: NAV_CREATE,  label: "Create",  Icon: PackagePlus   },
    { idx: NAV_BATCH,   label: "Batch",   Icon: Layers        },
    { idx: NAV_CONVERT, label: "Convert", Icon: ArrowLeftRight },
  ];

  function navigate(idx: number) {
    persistUIState({ active_nav: idx });
  }

  function toggleTheme() {
    const current = $uiState.theme;
    const isDark =
      current === "dark" ||
      (current === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    const next: "light" | "dark" = isDark ? "light" : "dark";
    persistUIState({ theme: next });
    applyTheme(next);
  }

  $: isDark =
    $uiState.theme === "dark" ||
    ($uiState.theme === "system" &&
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
</script>

<aside class="sidebar">
  <!-- Brand -->
  <div class="brand">
    <div class="brand-icon"><Archive size={16} color="var(--accent)" /></div>
    <span class="brand-name">ArchiveTools</span>
  </div>

  <div class="divider"></div>

  <!-- Navigation -->
  <nav class="nav">
    {#each navItems as { idx, label, Icon }}
      <button
        class="nav-item"
        class:active={$uiState.active_nav === idx}
        onclick={() => navigate(idx)}
        title={label}
      >
        <span class="nav-icon">
          <Icon size={16} />
        </span>
        <span class="nav-label">{label}</span>
      </button>
    {/each}
  </nav>

  <div class="spacer"></div>
  <div class="divider"></div>

  <!-- Bottom actions -->
  <div class="bottom-actions">
    <button class="icon-btn" onclick={toggleTheme} title={isDark ? "Light mode" : "Dark mode"}>
      {#if isDark}
        <Sun size={16} />
      {:else}
        <Moon size={16} />
      {/if}
    </button>
    <button class="icon-btn" title="Saved Passwords" onclick={() => (showPasswords = true)}>
      <KeyRound size={16} />
    </button>
    <button class="icon-btn" title="Settings" onclick={() => (showSettings = true)}>
      <Settings size={16} />
    </button>
  </div>
</aside>

{#if showSettings}
  <SettingsDialog on:close={() => (showSettings = false)} />
{/if}
{#if showPasswords}
  <PasswordManager on:close={() => (showPasswords = false)} />
{/if}

<style>
  .sidebar {
    width: 200px;
    min-width: 200px;
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 12px 10px;
    gap: 4px;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-right: 1px solid var(--glass-border);
    box-shadow: var(--shadow-sm);
  }

  /* ── Brand ────────────────────────────────────────────────── */

  .brand {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px 10px;
  }

  .brand-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: var(--accent-subtle);
    flex-shrink: 0;
  }

  .brand-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.3px;
  }

  /* ── Divider ──────────────────────────────────────────────── */

  .divider {
    height: 1px;
    background: var(--glass-border);
    margin: 4px 4px;
  }

  /* ── Navigation ───────────────────────────────────────────── */

  .nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 4px 0;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--text-2);
    font-size: 13px;
    font-family: var(--font-sans);
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: background 0.12s, color 0.12s, box-shadow 0.12s;
    width: 100%;
  }

  .nav-item:hover {
    background: var(--glass-inset);
    color: var(--text);
  }

  .nav-item.active {
    background: var(--accent-subtle);
    color: var(--accent);
    box-shadow: inset 0 0 0 1px rgba(0, 122, 255, 0.18);
  }

  .nav-icon {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }

  .nav-label { flex: 1; }

  /* ── Spacer ───────────────────────────────────────────────── */

  .spacer { flex: 1; }

  /* ── Bottom actions ───────────────────────────────────────── */

  .bottom-actions {
    display: flex;
    gap: 4px;
    padding: 4px 4px 2px;
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
    flex-shrink: 0;
  }

  .icon-btn:hover {
    background: var(--glass-inset);
    color: var(--text);
  }
</style>
