<script lang="ts">
  export let active = false;
  export let progress: number | null = null; // 0.0–1.0; null = indeterminate
</script>

{#if active}
  <div class="track">
    {#if progress === null}
      <div class="bar shimmer"></div>
    {:else}
      <div class="bar" style="width: {Math.round(progress * 100)}%"></div>
    {/if}
  </div>
{/if}

<style>
  .track {
    height: 2px;
    background: rgba(128, 128, 128, 0.12);
    overflow: hidden;
    flex-shrink: 0;
  }

  .bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), #5ac8fa, var(--accent));
    background-size: 200% 100%;
    transition: width 0.25s ease;
  }

  .bar.shimmer {
    width: 45%;
    animation: shimmer-slide 1.4s ease-in-out infinite;
  }

  @keyframes shimmer-slide {
    0%   { transform: translateX(-120%); }
    100% { transform: translateX(280%); }
  }
</style>
