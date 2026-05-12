import { get, writable } from "svelte/store";
import { getUIState, saveUIState, type UIState } from "../api/settings";

const _default: UIState = {
  theme: "system",
  active_nav: 1,
  recent_archives: [],
  last_archive_dir: "",
};

export const uiState = writable<UIState>({ ..._default });

export function applyTheme(theme: "system" | "light" | "dark"): void {
  const isDark =
    theme === "dark" ||
    (theme === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", isDark);
}

export async function loadUIState(): Promise<void> {
  const state = await getUIState();
  uiState.set(state);
  applyTheme(state.theme);
}

export async function persistUIState(patch: Partial<UIState>): Promise<void> {
  uiState.update((s) => ({ ...s, ...patch }));
  await saveUIState(get(uiState));
}

export async function addRecent(path: string): Promise<void> {
  const current = get(uiState);
  const recents = current.recent_archives.filter((p) => p !== path);
  recents.unshift(path);
  await persistUIState({ recent_archives: recents.slice(0, 15) });
}

export async function clearRecents(): Promise<void> {
  await persistUIState({ recent_archives: [] });
}
