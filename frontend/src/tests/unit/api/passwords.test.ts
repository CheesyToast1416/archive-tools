import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("$lib/api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

import { apiGet, apiPost, apiPut, apiDelete } from "$lib/api/client";
import {
  listPasswords,
  addPassword,
  updatePassword,
  deletePassword,
  getPasswordSecret,
  getKeyringStatus,
} from "$lib/api/passwords";

const get = vi.mocked(apiGet);
const post = vi.mocked(apiPost);
const put = vi.mocked(apiPut);
const del = vi.mocked(apiDelete);

const ENTRIES = [{ id: "1", label: "My Pass", hint: "hint" }];

beforeEach(() => {
  vi.clearAllMocks();
  get.mockResolvedValue(ENTRIES);
  post.mockResolvedValue(ENTRIES[0]);
  put.mockResolvedValue({ ok: true });
  del.mockResolvedValue(undefined);
});

describe("listPasswords", () => {
  it("GETs /passwords/", async () => {
    const r = await listPasswords();
    expect(get).toHaveBeenCalledWith("/passwords/");
    expect(r).toEqual(ENTRIES);
  });
});

describe("addPassword", () => {
  it("POSTs to /passwords/", async () => {
    await addPassword({ label: "My Pass", password: "secret", hint: "hint" });
    expect(post).toHaveBeenCalledWith("/passwords/", {
      label: "My Pass",
      password: "secret",
      hint: "hint",
    });
  });
});

describe("updatePassword", () => {
  it("PUTs to /passwords/:id", async () => {
    await updatePassword("1", { label: "New Label" });
    expect(put).toHaveBeenCalledWith("/passwords/1", { label: "New Label" });
  });
});

describe("deletePassword", () => {
  it("DELETEs /passwords/:id", async () => {
    await deletePassword("1");
    expect(del).toHaveBeenCalledWith("/passwords/1");
  });
});

describe("getPasswordSecret", () => {
  it("GETs /passwords/:id/secret", async () => {
    get.mockResolvedValue({ password: "s3cr3t" });
    const r = await getPasswordSecret("1");
    expect(get).toHaveBeenCalledWith("/passwords/1/secret");
    expect((r as { password: string }).password).toBe("s3cr3t");
  });
});

describe("getKeyringStatus", () => {
  it("GETs /passwords/keyring-status", async () => {
    get.mockResolvedValue({ keyring_available: true });
    const r = await getKeyringStatus();
    expect(get).toHaveBeenCalledWith("/passwords/keyring-status");
    expect((r as { keyring_available: boolean }).keyring_available).toBe(true);
  });
});
