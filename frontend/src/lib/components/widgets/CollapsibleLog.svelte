<script lang="ts">
  import { ChevronDown, ChevronRight } from "lucide-svelte";

  export let log: string[] = [];
  let expanded = false;

  $: if (log.some((l) => l.startsWith("✗"))) expanded = true;
</script>

{#if log.length > 0}
  <div class="log-wrap">
    <button class="toggle" onclick={() => (expanded = !expanded)}>
      {#if expanded}
        <ChevronDown size={13} />
      {:else}
        <ChevronRight size={13} />
      {/if}
      <span>Log</span>
      <span class="count">({log.length})</span>
    </button>
    {#if expanded}
      <pre class="log-body">{log.join("\n")}</pre>
    {/if}
  </div>
{/if}

<style>
  .log-wrap {
    border-top: 1px solid var(--glass-border);
    flex-shrink: 0;
  }

  .toggle {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 7px 12px;
    background: none;
    border: none;
    color: var(--text-2);
    font-size: 12px;
    font-family: var(--font-sans);
    cursor: pointer;
    width: 100%;
    text-align: left;
    transition: color 0.12s;
  }

  .toggle:hover { color: var(--text); }

  .count { color: var(--text-3); font-size: 11px; }

  .log-body {
    margin: 0;
    padding: 8px 12px 10px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-2);
    background: var(--glass-inset);
    max-height: 140px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.6;
  }
</style>
