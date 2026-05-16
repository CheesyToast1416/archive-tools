<script lang="ts">
  import {
    ChevronDown,
    ChevronRight,
    File,
    FileAudio,
    FileImage,
    FileText,
    FileVideo,
    Folder,
    FolderOpen,
    Minus,
    Plus,
  } from "lucide-svelte";
  import { createEventDispatcher, onDestroy, onMount } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
  import { open } from "@tauri-apps/plugin-dialog";

  export let names: string[] = [];
  export let editMode = false;

  const dispatch = createEventDispatcher<{
    entrySelected: string;
    entriesModified: { add: string[]; remove: string[] };
  }>();

  interface TreeNode {
    label: string;
    fullPath: string;
    isDir: boolean;
    children: TreeNode[];
    expanded: boolean;
  }

  let selected: string | null = null;
  let addedFiles: string[] = [];
  let removedPaths = new SvelteSet<string>();
  let unlisten: (() => void) | null = null;

  onMount(async () => {
    if (!editMode) return;
    _attachDrop();
  });

  onDestroy(() => unlisten?.());

  // eslint-disable-next-line svelte/infinite-reactive-loop
  $: if (editMode) _attachDrop();
  else {
    unlisten?.();
    unlisten = null;
  }

  async function _attachDrop() {
    if (unlisten) return;
    const win = getCurrentWebviewWindow();
    // eslint-disable-next-line svelte/infinite-reactive-loop
    unlisten = await win.onDragDropEvent((event) => {
      if (event.payload.type === "drop") {
        const paths: string[] = (event.payload as any).paths ?? [];
        if (paths.length) _addFiles(paths);
      }
    });
  }

  async function browseAdd() {
    const result = await open({ multiple: true });
    if (Array.isArray(result)) _addFiles(result);
  }

  function _addFiles(paths: string[]) {
    const newOnes = paths.filter((p) => !addedFiles.includes(p));
    addedFiles = [...addedFiles, ...newOnes];
  }

  $: tree = buildTree(names);

  function buildTree(paths: string[]): TreeNode[] {
    const root: TreeNode[] = [];
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const dirs = new Map<string, TreeNode>();

    function getOrCreateDir(path: string): TreeNode {
      if (dirs.has(path)) return dirs.get(path)!;
      const clean = path.replace(/\/$/, "");
      const sep = clean.lastIndexOf("/");
      const label = sep === -1 ? clean : clean.slice(sep + 1);
      const node: TreeNode = {
        label,
        fullPath: path,
        isDir: true,
        children: [],
        expanded: paths.length <= 50,
      };
      if (sep === -1) root.push(node);
      else getOrCreateDir(clean.slice(0, sep) + "/").children.push(node);
      dirs.set(path, node);
      return node;
    }

    for (const p of paths) {
      if (p.endsWith("/")) {
        getOrCreateDir(p);
        continue;
      }
      const sep = p.lastIndexOf("/");
      const label = sep === -1 ? p : p.slice(sep + 1);
      const node: TreeNode = { label, fullPath: p, isDir: false, children: [], expanded: false };
      if (sep === -1) root.push(node);
      else getOrCreateDir(p.slice(0, sep) + "/").children.push(node);
    }
    return root;
  }

  function selectNode(node: TreeNode) {
    if (node.isDir) {
      node.expanded = !node.expanded;
      // eslint-disable-next-line svelte/no-reactive-reassign
      tree = tree;
      return;
    }
    selected = node.fullPath;
    dispatch("entrySelected", node.fullPath);
  }

  function onKeyDown(e: KeyboardEvent, node: TreeNode) {
    if (!editMode) return;
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      markRemove(node);
    }
  }

  function markRemove(node: TreeNode) {
    const mark = (n: TreeNode) => {
      if (n.fullPath) removedPaths.add(n.fullPath);
      n.children.forEach(mark);
    };
    mark(node);
    removedPaths = removedPaths;
  }

  export function saveEdits() {
    dispatch("entriesModified", { add: addedFiles, remove: Array.from(removedPaths) });
  }

  export function cancelEdits() {
    addedFiles = [];
    removedPaths = new SvelteSet();
  }

  interface FlatRow {
    node: TreeNode;
    depth: number;
  }

  function flatten(nodes: TreeNode[], depth = 0): FlatRow[] {
    const out: FlatRow[] = [];
    for (const n of nodes) {
      out.push({ node: n, depth });
      if (n.isDir && n.expanded) out.push(...flatten(n.children, depth + 1));
    }
    return out;
  }

  $: rows = flatten(tree);

  function fileIcon(label: string) {
    const ext = label.split(".").pop()?.toLowerCase() ?? "";
    if (["jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "ico"].includes(ext)) return FileImage;
    if (["mp4", "mkv", "avi", "mov", "webm", "m4v"].includes(ext)) return FileVideo;
    if (["mp3", "wav", "ogg", "flac", "aac", "m4a", "opus"].includes(ext)) return FileAudio;
    if (
      [
        "txt",
        "md",
        "py",
        "js",
        "ts",
        "json",
        "yaml",
        "toml",
        "xml",
        "html",
        "css",
        "sh",
        "log",
      ].includes(ext)
    )
      return FileText;
    return File;
  }
</script>

<div class="tree-wrap" role="tree" tabindex="0">
  <div class="tree-header">
    <span class="section-label" style="margin:0">Contents</span>
    <span class="entry-count">{names.length}</span>
    {#if editMode}
      <button class="add-btn" onclick={browseAdd}>
        <Plus size={12} />
        Add Files
      </button>
    {/if}
  </div>

  <!-- Staged additions in edit mode -->
  {#if editMode}
    {#each addedFiles as f (f)}
      <div class="row added" style="padding-left: 14px">
        <Plus size={12} class="row-icon" />
        <span class="row-label">{f.split(/[\\/]/).pop()}</span>
      </div>
    {/each}
  {/if}

  {#each rows as { node, depth } (node.fullPath)}
    {@const removed = removedPaths.has(node.fullPath)}
    <!-- svelte-ignore a11y-interactive-supports-focus -->
    <div
      class="row"
      class:selected={selected === node.fullPath && !node.isDir}
      class:removed
      class:dir={node.isDir}
      style="padding-left: {14 + depth * 18}px"
      role="treeitem"
      aria-selected={selected === node.fullPath}
      onclick={() => selectNode(node)}
      onkeydown={(e) => onKeyDown(e, node)}
    >
      <span class="row-icon">
        {#if node.isDir}
          {#if node.expanded}
            <ChevronDown size={13} />
            <FolderOpen size={13} />
          {:else}
            <ChevronRight size={13} />
            <Folder size={13} />
          {/if}
        {:else if removed}
          <Minus size={13} />
        {:else}
          <svelte:component this={fileIcon(node.label)} size={13} />
        {/if}
      </span>
      <span class="row-label">{node.label}</span>
    </div>
  {/each}
</div>

<style>
  .tree-wrap {
    flex: 1;
    overflow-y: auto;
    font-size: 12.5px;
    outline: none;
    padding-bottom: 8px;
  }

  /* ── Header ──────────────────────────────────────────────── */

  .tree-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px 6px;
    position: sticky;
    top: 0;
    background: var(--glass);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-bottom: 1px solid var(--glass-border);
    z-index: 1;
  }

  .entry-count {
    font-size: 11px;
    color: var(--text-3);
    background: var(--glass-inset);
    padding: 1px 6px;
    border-radius: 10px;
    font-weight: 500;
  }

  .add-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: auto;
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-sans);
    font-weight: 500;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: var(--glass);
    color: var(--accent);
    cursor: pointer;
    transition: background 0.12s;
  }

  .add-btn:hover {
    background: var(--accent-subtle);
  }

  /* ── Rows ────────────────────────────────────────────────── */

  .row {
    display: flex;
    align-items: center;
    gap: 5px;
    padding-top: 3px;
    padding-bottom: 3px;
    padding-right: 10px;
    cursor: pointer;
    color: var(--text);
    user-select: none;
    border-radius: 0;
    transition: background 0.1s;
    position: relative;
  }

  .row::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 2px;
    background: transparent;
    transition: background 0.12s;
  }

  .row:hover {
    background: var(--glass-inset);
  }

  .row:hover::before {
    background: var(--glass-border);
  }

  .row.selected {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .row.selected::before {
    background: var(--accent);
  }

  .row.removed {
    color: var(--error);
    text-decoration: line-through;
    opacity: 0.7;
  }

  .row.dir {
    color: var(--text);
  }

  .row.added {
    color: var(--success);
  }

  .row-icon {
    display: flex;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
    color: inherit;
    opacity: 0.7;
  }

  .row-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    font-weight: 400;
  }

  .row.dir .row-label {
    font-weight: 500;
  }
</style>
