import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/svelte";

vi.mock("$lib/api/passwords", () => ({
  listPasswords: vi.fn().mockResolvedValue([]),
  getPasswordSecret: vi.fn().mockResolvedValue({ password: "" }),
}));

import PasswordPrompt from "$lib/components/dialogs/PasswordPrompt.svelte";

describe("PasswordPrompt", () => {
  it("renders with default message", () => {
    const { getByText } = render(PasswordPrompt, {
      props: { onSubmit: vi.fn(), onCancel: vi.fn() },
    });
    expect(getByText("Enter password:")).toBeInTheDocument();
  });

  it("renders with custom message", () => {
    const { getByText } = render(PasswordPrompt, {
      props: { message: "Archive is locked", onSubmit: vi.fn(), onCancel: vi.fn() },
    });
    expect(getByText("Archive is locked")).toBeInTheDocument();
  });

  it("renders Unlock and Cancel buttons", () => {
    const { getByText } = render(PasswordPrompt, {
      props: { onSubmit: vi.fn(), onCancel: vi.fn() },
    });
    expect(getByText("Unlock")).toBeInTheDocument();
    expect(getByText("Cancel")).toBeInTheDocument();
  });

  it("calls onSubmit with typed password when Unlock clicked", async () => {
    const onSubmit = vi.fn();
    const { getByText, getByPlaceholderText } = render(PasswordPrompt, {
      props: { onSubmit, onCancel: vi.fn() },
    });
    const input = getByPlaceholderText("Archive password");
    await fireEvent.input(input, { target: { value: "secret123" } });
    await fireEvent.click(getByText("Unlock"));
    expect(onSubmit).toHaveBeenCalledWith("secret123");
  });

  it("calls onCancel when Cancel button clicked", async () => {
    const onCancel = vi.fn();
    const { getByText } = render(PasswordPrompt, {
      props: { onSubmit: vi.fn(), onCancel },
    });
    await fireEvent.click(getByText("Cancel"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("calls onSubmit on Enter key", async () => {
    const onSubmit = vi.fn();
    render(PasswordPrompt, { props: { onSubmit, onCancel: vi.fn() } });
    await fireEvent.keyDown(window, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalled();
  });

  it("calls onCancel on Escape key", async () => {
    const onCancel = vi.fn();
    render(PasswordPrompt, { props: { onSubmit: vi.fn(), onCancel } });
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(onCancel).toHaveBeenCalled();
  });

  it("calls onCancel when X button in header is clicked", async () => {
    const onCancel = vi.fn();
    const { container } = render(PasswordPrompt, {
      props: { onSubmit: vi.fn(), onCancel },
    });
    await fireEvent.click(container.querySelector(".close-btn")!);
    expect(onCancel).toHaveBeenCalled();
  });
});
