<script lang="ts">
  import { KeyRound, Plus, ShieldAlert, Trash2, X } from "@lucide/svelte";
  import { onMount } from "svelte";
  import {
    addPassword,
    deletePassword,
    getKeyringStatus,
    listPasswords,
    type PasswordEntry,
  } from "$lib/api/passwords";

  let { close } = $props();
  let entries: PasswordEntry[] = $state([]);
  let keyringAvailable = $state(true);
  let newLabel = $state("");
  let newPassword = $state("");
  let newHint = $state("");
  let adding = $state(false);
  let error = $state("");
  let confirmDeleteId: string | null = $state(null);

  onMount(async () => {
    entries = await listPasswords().catch(() => []);
    const ks = await getKeyringStatus().catch(() => ({ keyring_available: false }));
    keyringAvailable = ks.keyring_available;
  });

  async function doAdd() {
    if (!newLabel || !newPassword) return;
    error = "";
    try {
      const entry = await addPassword({ label: newLabel, password: newPassword, hint: newHint });
      entries = [...entries, entry];
      newLabel = "";
      newPassword = "";
      newHint = "";
      adding = false;
    } catch (e) {
      error = String(e);
    }
  }

  function requestDelete(id: string) {
    confirmDeleteId = id;
  }

  async function confirmDelete() {
    if (!confirmDeleteId) return;
    await deletePassword(confirmDeleteId).catch(() => {});
    entries = entries.filter((e) => e.id !== confirmDeleteId);
    confirmDeleteId = null;
  }
</script>

<div class="overlay">
  <div class="dialog glass-raised">
    <div class="dialog-header">
      <div class="header-icon">
        <KeyRound size={16} color="var(--accent)" />
      </div>
      <span class="dialog-title">Saved Passwords</span>
      <button class="close-btn" onclick={() => close()}>
        <X size={14} />
      </button>
    </div>

    {#if !keyringAvailable}
      <div class="warn-banner">
        <ShieldAlert size={14} />
        OS keyring unavailable — passwords use local encryption only.
      </div>
    {/if}

    <div class="dialog-body">
      {#if entries.length === 0 && !adding}
        <div class="empty-state">
          <KeyRound size={28} strokeWidth={1.2} />
          <p>No saved passwords</p>
        </div>
      {/if}

      {#each entries as entry (entry.id)}
        <div class="entry-row">
          <div class="entry-icon">
            <KeyRound size={14} color="var(--accent)" />
          </div>
          <div class="entry-info">
            <span class="entry-label">{entry.label}</span>
            {#if entry.hint}<span class="entry-hint">{entry.hint}</span>{/if}
          </div>
          {#if confirmDeleteId === entry.id}
            <div class="confirm-row">
              <span class="confirm-text">Delete?</span>
              <button class="btn btn-danger" onclick={confirmDelete}>Yes</button>
              <button class="btn" onclick={() => (confirmDeleteId = null)}>No</button>
            </div>
          {:else}
            <button class="icon-btn" onclick={() => requestDelete(entry.id)} title="Delete">
              <Trash2 size={14} />
            </button>
          {/if}
        </div>
      {/each}

      {#if adding}
        <div class="add-form">
          <input class="input" bind:value={newLabel} placeholder="Label (e.g. Work archives)" />
          <input class="input" type="password" bind:value={newPassword} placeholder="Password" />
          <input
            class="input"
            bind:value={newHint}
            placeholder="Hint (optional, stored in plaintext)"
          />
          {#if error}<p class="error-text">{error}</p>{/if}
          <div class="add-actions">
            <button
              class="btn"
              onclick={() => {
                adding = false;
                error = "";
              }}
              >Cancel
            </button>
            <button class="btn btn-primary" onclick={doAdd} disabled={!newLabel || !newPassword}>
              <Plus size={13} />
              Add Password
            </button>
          </div>
        </div>
      {/if}
    </div>

    <div class="dialog-footer">
      {#if !adding}
        <button class="btn btn-primary" onclick={() => (adding = true)}>
          <Plus size={13} />
          Add Password
        </button>
      {/if}
      <div style="flex:1"></div>
      <button class="btn" onclick={() => close()}>Done</button>
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
    width: 420px;
    max-height: 70vh;
    display: flex;
    flex-direction: column;
    border-radius: 16px;
    box-shadow: var(--shadow-xl);
    overflow: hidden;
  }

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

  .warn-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: var(--warning-subtle);
    color: var(--warning);
    font-size: 12px;
    font-weight: 500;
    border-bottom: 1px solid rgba(255, 159, 10, 0.2);
  }

  .dialog-body {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 32px 20px;
    color: var(--text-3);
    font-size: 13px;
    text-align: center;
  }

  .entry-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--glass-inset);
    border: 1px solid var(--glass-border);
    transition: background 0.1s;
  }

  .entry-row:hover {
    background: var(--glass);
  }

  .entry-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: var(--accent-subtle);
    flex-shrink: 0;
  }

  .entry-info {
    flex: 1;
    overflow: hidden;
  }

  .entry-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    display: block;
  }

  .entry-hint {
    font-size: 11px;
    color: var(--text-3);
    display: block;
    margin-top: 1px;
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
    transition:
      background 0.12s,
      color 0.12s;
    flex-shrink: 0;
  }

  .icon-btn:hover {
    background: var(--error-subtle);
    color: var(--error);
  }

  .confirm-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .confirm-text {
    font-size: 12px;
    color: var(--text-2);
  }

  .add-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    background: var(--glass);
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    margin-top: 4px;
  }

  .add-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .error-text {
    font-size: 12px;
    color: var(--error);
    margin: 0;
  }

  .dialog-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--glass-border);
    flex-shrink: 0;
  }
</style>
