import { apiGet, apiPut } from "./client";

export interface AppSettings {
  smart_extraction: boolean;
  trash_after_extract: boolean;
  default_output_dir: string;
  trash_after_create: boolean;
  trash_after_batch: boolean;
  default_password_encoding: string;
  default_filename_encoding: string;
  notifications_enabled: boolean;
}

export interface UIState {
  theme: "system" | "light" | "dark";
  active_nav: number;
  recent_archives: string[];
  last_archive_dir: string;
}

export function getAppSettings(): Promise<AppSettings> {
  return apiGet("/settings/app");
}

export function saveAppSettings(settings: AppSettings): Promise<{ ok: boolean }> {
  return apiPut("/settings/app", settings);
}

export function getUIState(): Promise<UIState> {
  return apiGet("/settings/ui");
}

export function saveUIState(state: UIState): Promise<{ ok: boolean }> {
  return apiPut("/settings/ui", state);
}
