<script lang="ts">
  import { Eye, EyeOff, KeyRound } from "lucide-svelte";
  import { getPasswordSecret, listPasswords, type PasswordEntry } from "$lib/api/passwords";

  export let value = "";
  export let placeholder = "Password";
  export let disabled = false;

  let showPassword = false;
  let passwords: PasswordEntry[] = [];
  let showPicker = false;

  async function togglePicker() {
    if (!showPicker) {
      passwords = await listPasswords().catch(() => []);
    }
    showPicker = !showPicker;
  }

  async function selectPassword(entry: PasswordEntry) {
    const result = await getPasswordSecret(entry.id).catch(() => null);
    if (result) value = result.password;
    showPicker = false;
  }
</script>

<div class="field-wrap">
  <div class="input-row">
    <input
      class="input"
      type={showPassword ? "text" : "password"}
      bind:value
      {placeholder}
      {disabled}
    />
    <button
      class="icon-btn"
      type="button"
      onclick={() => (showPassword = !showPassword)}
      title={showPassword ? "Hide password" : "Show password"}
      tabindex="-1"
    >
      {#if showPassword}
        <EyeOff size={14} />
      {:else}
        <Eye size={14} />
      {/if}
    </button>
    <button
      class="icon-btn"
      type="button"
      onclick={togglePicker}
      title="Saved passwords"
      tabindex="-1"
    >
      <KeyRound size={14} />
    </button>
  </div>

  {#if showPicker}
    <div class="picker-dropdown">
      {#if passwords.length === 0}
        <div class="picker-empty">No saved passwords</div>
      {:else}
        {#each passwords as entry (entry.id)}
          <button class="picker-item" onclick={() => selectPassword(entry)}>
            <span class="picker-label">{entry.label}</span>
            {#if entry.hint}<span class="picker-hint">{entry.hint}</span>{/if}
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .field-wrap {
    position: relative;
  }

  .input-row {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .input-row .input {
    flex: 1;
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    color: var(--text-2);
    cursor: pointer;
    transition:
      background 0.12s,
      color 0.12s;
  }

  .icon-btn:hover {
    background: var(--glass-raised);
    color: var(--text);
  }

  /* Picker dropdown */
  .picker-dropdown {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    z-index: 200;
    background: var(--glass-overlay);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    box-shadow: var(--shadow-lg);
    overflow: hidden;
  }

  .picker-item {
    display: flex;
    flex-direction: column;
    width: 100%;
    padding: 9px 12px;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s;
  }

  .picker-item:hover {
    background: var(--accent-subtle);
  }

  .picker-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
  }

  .picker-hint {
    font-size: 11px;
    color: var(--text-3);
    margin-top: 1px;
  }

  .picker-empty {
    padding: 12px;
    font-size: 12px;
    color: var(--text-3);
    text-align: center;
  }
</style>
