import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export interface PasswordEntry {
  id: string;
  label: string;
  hint: string;
}

export function listPasswords(): Promise<PasswordEntry[]> {
  return apiGet("/passwords/");
}

export function addPassword(params: {
  label: string;
  password: string;
  hint?: string;
}): Promise<PasswordEntry> {
  return apiPost("/passwords/", params);
}

export function updatePassword(
  id: string,
  params: { label?: string; password?: string; hint?: string },
): Promise<{ ok: boolean }> {
  return apiPut(`/passwords/${id}`, params);
}

export function deletePassword(id: string): Promise<void> {
  return apiDelete(`/passwords/${id}`);
}

export function getPasswordSecret(id: string): Promise<{ password: string }> {
  return apiGet(`/passwords/${id}/secret`);
}

export function getKeyringStatus(): Promise<{ keyring_available: boolean }> {
  return apiGet("/passwords/keyring-status");
}
