import { get, writable } from "svelte/store";
import { getAppSettings, saveAppSettings, type AppSettings } from "../api/settings";

const _default: AppSettings = {
  smart_extraction: true,
  trash_after_extract: false,
  default_output_dir: "",
  trash_after_create: false,
  trash_after_batch: false,
  default_password_encoding: "",
  default_filename_encoding: "",
  notifications_enabled: true,
};

export const appSettings = writable<AppSettings>({ ..._default });

export async function loadAppSettings(): Promise<void> {
  const s = await getAppSettings();
  appSettings.set(s);
}

export async function persistAppSettings(
  patch: Partial<AppSettings>,
): Promise<void> {
  appSettings.update((s) => ({ ...s, ...patch }));
  await saveAppSettings(get(appSettings));
}
