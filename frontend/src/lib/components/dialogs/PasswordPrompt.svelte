<script lang="ts">
  import { KeyRound, X } from "lucide-svelte";
  import PasswordField from "../widgets/PasswordField.svelte";

  export let message = "Enter password:";
  export let onSubmit: (password: string) => void;
  export let onCancel: () => void;

  let password = "";

  function submit() { onSubmit(password); }
  function handleKey(e: KeyboardEvent) {
    if (e.key === "Enter") submit();
    if (e.key === "Escape") onCancel();
  }
</script>

<svelte:window onkeydown={handleKey} />

<div class="overlay">
  <div class="dialog glass-raised">
    <div class="dialog-header">
      <div class="header-icon">
        <KeyRound size={16} color="var(--accent)" />
      </div>
      <span class="dialog-title">Password Required</span>
      <button class="close-btn" onclick={onCancel}><X size={14} /></button>
    </div>
    <div class="dialog-body">
      <p class="message">{message}</p>
      <PasswordField bind:value={password} placeholder="Archive password" />
    </div>
    <div class="dialog-footer">
      <button class="btn" onclick={onCancel}>Cancel</button>
      <button class="btn btn-primary" onclick={submit}>Unlock</button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.40);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 500;
  }

  .dialog {
    width: 360px;
    border-radius: 14px;
    box-shadow: var(--shadow-xl);
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px 12px;
    border-bottom: 1px solid var(--glass-border);
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

  .dialog-title { font-size: 14px; font-weight: 600; color: var(--text); flex: 1; }

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
    transition: background 0.12s, color 0.12s;
  }

  .close-btn:hover { background: var(--glass-inset); color: var(--text); }

  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
  }

  .message { margin: 0; font-size: 13px; color: var(--text-2); }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--glass-border);
  }
</style>
