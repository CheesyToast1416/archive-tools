import { writable } from "svelte/store";

/**
 * Set this to a path before navigating to the Extract panel.
 * ExtractPanel reads it on mount, opens the archive, then resets to null.
 */
export const pendingArchivePath = writable<string | null>(null);
