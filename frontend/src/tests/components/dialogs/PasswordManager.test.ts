import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$lib/api/passwords", () => ({
  listPasswords: vi.fn().mockResolvedValue([
    { id: "1", label: "GitHub", hint: "work account" },
    { id: "2", label: "MyServer", hint: "" },
  ]),
  addPassword: vi.fn().mockResolvedValue({ id: "3", label: "New", hint: "" }),
  deletePassword: vi.fn().mockResolvedValue(undefined),
  getKeyringStatus: vi.fn().mockResolvedValue({ keyring_available: true }),
  getPasswordSecret: vi.fn().mockResolvedValue({ password: "" }),
  updatePassword: vi.fn().mockResolvedValue({ ok: true }),
}));

const ENTRIES = [
  { id: "1", label: "GitHub", hint: "work account" },
  { id: "2", label: "MyServer", hint: "" },
];

import { listPasswords, deletePassword, getKeyringStatus } from "$lib/api/passwords";
import PasswordManager from "$lib/components/dialogs/PasswordManager.svelte";

const mockList = vi.mocked(listPasswords);
const mockDelete = vi.mocked(deletePassword);
const mockKeyring = vi.mocked(getKeyringStatus);

// PasswordManager uses $props() for the close callback (Svelte 5 runes mode)
const withClose = (handler = vi.fn()) => ({ props: { close: handler } });

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue(ENTRIES);
  mockKeyring.mockResolvedValue({ keyring_available: true });
});

describe("PasswordManager", () => {
  it("loads and renders password entries on mount", async () => {
    const { findByText } = render(PasswordManager, withClose());
    expect(await findByText("GitHub")).toBeInTheDocument();
    expect(await findByText("work account")).toBeInTheDocument();
    expect(await findByText("MyServer")).toBeInTheDocument();
  });

  it("calls listPasswords and getKeyringStatus on mount", async () => {
    render(PasswordManager, withClose());
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    expect(mockKeyring).toHaveBeenCalled();
  });

  it("shows keyring unavailable warning when keyring not available", async () => {
    mockKeyring.mockResolvedValue({ keyring_available: false });
    const { findByText } = render(PasswordManager, withClose());
    expect(await findByText(/OS keyring unavailable/)).toBeInTheDocument();
  });

  it("does not show keyring warning when keyring is available", async () => {
    const { queryByText } = render(PasswordManager, withClose());
    await waitFor(() => expect(mockKeyring).toHaveBeenCalled());
    expect(queryByText(/OS keyring unavailable/)).toBeNull();
  });

  it("shows empty state when no passwords", async () => {
    mockList.mockResolvedValue([]);
    const { findByText } = render(PasswordManager, withClose());
    expect(await findByText("No saved passwords")).toBeInTheDocument();
  });

  it("shows confirm UI after delete button clicked", async () => {
    const { findAllByTitle, findByText } = render(PasswordManager, withClose());
    const deleteBtns = await findAllByTitle("Delete");
    await fireEvent.click(deleteBtns[0]);
    expect(await findByText("Delete?")).toBeInTheDocument();
  });

  it("confirms delete and removes entry", async () => {
    const { findAllByTitle, findByText, queryByText } = render(PasswordManager, withClose());
    const deleteBtns = await findAllByTitle("Delete");
    await fireEvent.click(deleteBtns[0]);
    await fireEvent.click(await findByText("Yes"));
    expect(mockDelete).toHaveBeenCalledWith("1");
    await waitFor(() => expect(queryByText("GitHub")).toBeNull());
  });

  it("cancels delete when No is clicked", async () => {
    const { findAllByTitle, findByText, queryByText } = render(PasswordManager, withClose());
    const deleteBtns = await findAllByTitle("Delete");
    await fireEvent.click(deleteBtns[0]);
    await fireEvent.click(await findByText("No"));
    expect(mockDelete).not.toHaveBeenCalled();
    expect(queryByText("Delete?")).toBeNull();
  });

  it("calls close callback when X button clicked", async () => {
    const closeHandler = vi.fn();
    const { container } = render(PasswordManager, withClose(closeHandler));
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    await fireEvent.click(container.querySelector(".close-btn")!);
    expect(closeHandler).toHaveBeenCalled();
  });
});
