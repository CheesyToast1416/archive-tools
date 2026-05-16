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

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue(ENTRIES);
  mockKeyring.mockResolvedValue({ keyring_available: true });
});

describe("PasswordManager", () => {
  it("loads and renders password entries on mount", async () => {
    const { findByText } = render(PasswordManager, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ...({ events: { close: vi.fn() } } as any),
      events: { close: vi.fn() },
    });
    expect(await findByText("GitHub")).toBeInTheDocument();
    expect(await findByText("work account")).toBeInTheDocument();
    expect(await findByText("MyServer")).toBeInTheDocument();
  });

  it("calls listPasswords and getKeyringStatus on mount", async () => {
    render(PasswordManager, { events: { close: vi.fn() } } as never);
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    expect(mockKeyring).toHaveBeenCalled();
  });

  it("shows keyring unavailable warning when keyring not available", async () => {
    mockKeyring.mockResolvedValue({ keyring_available: false });
    const { findByText } = render(PasswordManager, { events: { close: vi.fn() } } as never);
    expect(await findByText(/OS keyring unavailable/)).toBeInTheDocument();
  });

  it("does not show keyring warning when keyring is available", async () => {
    const { queryByText } = render(PasswordManager, { events: { close: vi.fn() } } as never);
    await waitFor(() => expect(mockKeyring).toHaveBeenCalled());
    expect(queryByText(/OS keyring unavailable/)).toBeNull();
  });

  it("shows empty state when no passwords", async () => {
    mockList.mockResolvedValue([]);
    const { findByText } = render(PasswordManager, { events: { close: vi.fn() } } as never);
    expect(await findByText("No saved passwords")).toBeInTheDocument();
  });

  it("shows confirm UI after delete button clicked", async () => {
    const { findAllByTitle, findByText } = render(PasswordManager, {
      events: { close: vi.fn() },
    } as never);
    const deleteBtns = await findAllByTitle("Delete");
    await fireEvent.click(deleteBtns[0]);
    expect(await findByText("Delete?")).toBeInTheDocument();
  });

  it("confirms delete and removes entry", async () => {
    const { findAllByTitle, findByText, queryByText } = render(PasswordManager, {
      events: { close: vi.fn() },
    } as never);
    const deleteBtns = await findAllByTitle("Delete");
    await fireEvent.click(deleteBtns[0]);
    await fireEvent.click(await findByText("Yes"));
    expect(mockDelete).toHaveBeenCalledWith("1");
    await waitFor(() => expect(queryByText("GitHub")).toBeNull());
  });

  it("cancels delete when No is clicked", async () => {
    const { findAllByTitle, findByText, queryByText } = render(PasswordManager, {
      events: { close: vi.fn() },
    } as never);
    const deleteBtns = await findAllByTitle("Delete");
    await fireEvent.click(deleteBtns[0]);
    await fireEvent.click(await findByText("No"));
    expect(mockDelete).not.toHaveBeenCalled();
    expect(queryByText("Delete?")).toBeNull();
  });

  it("dispatches close event when X button clicked", async () => {
    const closeHandler = vi.fn();
    const { container } = render(PasswordManager, {
      events: { close: closeHandler },
    } as never);
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    await fireEvent.click(container.querySelector(".close-btn")!);
    expect(closeHandler).toHaveBeenCalled();
  });
});
