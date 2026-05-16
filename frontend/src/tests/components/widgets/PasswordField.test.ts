import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/svelte";

vi.mock("$lib/api/passwords", () => ({
  listPasswords: vi.fn().mockResolvedValue([
    { id: "1", label: "GitHub", hint: "work account" },
    { id: "2", label: "Server", hint: "" },
  ]),
  getPasswordSecret: vi.fn().mockResolvedValue({ password: "mySecret123" }),
}));

import { listPasswords, getPasswordSecret } from "$lib/api/passwords";
import PasswordField from "$lib/components/widgets/PasswordField.svelte";

const mockList = vi.mocked(listPasswords);
const mockGet = vi.mocked(getPasswordSecret);

beforeEach(() => vi.clearAllMocks());

describe("PasswordField", () => {
  it("renders a password input by default", () => {
    const { container } = render(PasswordField);
    expect(container.querySelector("input[type=password]")).toBeInTheDocument();
  });

  it("shows text when eye button is clicked", async () => {
    const { container, getByTitle } = render(PasswordField);
    await fireEvent.click(getByTitle("Show password"));
    expect(container.querySelector("input[type=text]")).toBeInTheDocument();
  });

  it("toggles back to password on second click", async () => {
    const { container, getByTitle } = render(PasswordField);
    await fireEvent.click(getByTitle("Show password"));
    await fireEvent.click(getByTitle("Hide password"));
    expect(container.querySelector("input[type=password]")).toBeInTheDocument();
  });

  it("opens picker and lists passwords on key button click", async () => {
    const { getByTitle, findByText } = render(PasswordField);
    await fireEvent.click(getByTitle("Saved passwords"));
    expect(mockList).toHaveBeenCalled();
    expect(await findByText("GitHub")).toBeInTheDocument();
    expect(await findByText("work account")).toBeInTheDocument();
  });

  it("selecting a picker entry calls getPasswordSecret and closes picker", async () => {
    const { getByTitle, findByText, queryByText } = render(PasswordField);
    await fireEvent.click(getByTitle("Saved passwords"));
    const item = await findByText("GitHub");
    await fireEvent.click(item);
    expect(mockGet).toHaveBeenCalledWith("1");
    await waitFor(() => expect(queryByText("GitHub")).toBeNull());
  });

  it("disables input when disabled prop is true", () => {
    const { container } = render(PasswordField, { props: { disabled: true } });
    expect(container.querySelector("input")).toBeDisabled();
  });

  it("shows placeholder text", () => {
    const { container } = render(PasswordField, { props: { placeholder: "Archive password" } });
    expect(container.querySelector("input")).toHaveAttribute("placeholder", "Archive password");
  });

  it("shows empty picker message when no passwords", async () => {
    mockList.mockResolvedValueOnce([]);
    const { getByTitle, findByText } = render(PasswordField);
    await fireEvent.click(getByTitle("Saved passwords"));
    expect(await findByText("No saved passwords")).toBeInTheDocument();
  });
});
