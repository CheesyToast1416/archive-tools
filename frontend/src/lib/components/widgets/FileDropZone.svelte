<script lang="ts">
  import { Archive } from "lucide-svelte";
  import { open } from "@tauri-apps/plugin-dialog";
  import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
  import { ARCHIVE_EXTENSIONS } from "$lib/constants";
  import { createEventDispatcher, onDestroy, onMount } from "svelte";

  const dispatch = createEventDispatcher<{ path: string }>();

  let hovering = false;
  let unlisten: (() => void) | null = null;

  onMount(async () => {
    const win = getCurrentWebviewWindow();
    unlisten = await win.onDragDropEvent((event) => {
      if (event.payload.type === "over") {
        hovering = true;
      } else if (event.payload.type === "leave") {
        hovering = false;
      } else if (event.payload.type === "drop") {
        hovering = false;
        const paths: string[] = (event.payload as any).paths ?? [];
        if (paths.length > 0) dispatch("path", paths[0]);
      }
    });
  });

  onDestroy(() => unlisten?.());

  async function browse() {
    const path = await open({
      multiple: false,
      filters: [{ name: "Archives", extensions: ARCHIVE_EXTENSIONS }],
    });
    if (typeof path === "string") dispatch("path", path);
  }
</script>

<div
  class="drop-zone"
  class:hovering
  role="button"
  tabindex="0"
  onkeydown={(e) => e.key === "Enter" && browse()}
>
  <div class="icon-wrap" class:hovering>
    <Archive size={36} strokeWidth={1.5} />
  </div>
  <p class="hint">Drop an archive here</p>
  <p class="hint-sub">or</p>
  <button class="btn" onclick={browse}>Browse Files</button>
</div>

<style>
  .drop-zone {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    border: 1.5px dashed var(--glass-border);
    border-radius: 16px;
    margin: 16px;
    padding: 40px 24px;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    transition:
      background 0.2s,
      border-color 0.2s,
      box-shadow 0.2s;
    cursor: default;
  }

  .drop-zone.hovering {
    background: var(--glass-raised);
    border-color: var(--accent);
    box-shadow: var(--accent-glow), var(--shadow-md);
  }

  .icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 72px;
    height: 72px;
    border-radius: 20px;
    background: var(--glass-inset);
    border: 1px solid var(--glass-border);
    color: var(--text-3);
    transition:
      background 0.2s,
      color 0.2s;
  }

  .icon-wrap.hovering {
    background: var(--accent-subtle);
    color: var(--accent);
    border-color: rgba(0, 122, 255, 0.25);
  }

  .hint {
    margin: 0;
    color: var(--text-2);
    font-size: 14px;
    font-weight: 500;
  }

  .hint-sub {
    margin: 0;
    color: var(--text-3);
    font-size: 12px;
  }
</style>
