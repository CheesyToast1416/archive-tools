import { describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/svelte";
import CollapsibleLog from "$lib/components/widgets/CollapsibleLog.svelte";

describe("CollapsibleLog", () => {
  it("renders nothing when log is empty", () => {
    const { container } = render(CollapsibleLog, { props: { log: [] } });
    expect(container.querySelector(".log-wrap")).toBeNull();
  });

  it("shows toggle button when log has entries", () => {
    const { getByText } = render(CollapsibleLog, { props: { log: ["line 1"] } });
    expect(getByText("Log")).toBeInTheDocument();
  });

  it("shows correct count in badge", () => {
    const { getByText } = render(CollapsibleLog, { props: { log: ["a", "b", "c"] } });
    expect(getByText("(3)")).toBeInTheDocument();
  });

  it("log body is hidden by default", () => {
    const { container } = render(CollapsibleLog, { props: { log: ["line 1"] } });
    expect(container.querySelector(".log-body")).toBeNull();
  });

  it("expands on toggle button click", async () => {
    const { getByText, container } = render(CollapsibleLog, { props: { log: ["line 1"] } });
    await fireEvent.click(getByText("Log"));
    expect(container.querySelector(".log-body")).toBeInTheDocument();
    expect(container.querySelector(".log-body")?.textContent).toContain("line 1");
  });

  it("collapses again on second click", async () => {
    const { getByText, container } = render(CollapsibleLog, { props: { log: ["line 1"] } });
    await fireEvent.click(getByText("Log"));
    await fireEvent.click(getByText("Log"));
    expect(container.querySelector(".log-body")).toBeNull();
  });

  it("auto-expands when log contains an error line (✗)", async () => {
    const { container, rerender } = render(CollapsibleLog, { props: { log: ["✓ OK"] } });
    expect(container.querySelector(".log-body")).toBeNull();
    await rerender({ log: ["✓ OK", "✗ Failed"] });
    expect(container.querySelector(".log-body")).toBeInTheDocument();
  });

  it("shows all log lines joined by newline", async () => {
    const { getByText, container } = render(CollapsibleLog, {
      props: { log: ["line A", "line B"] },
    });
    await fireEvent.click(getByText("Log"));
    expect(container.querySelector(".log-body")?.textContent).toContain("line A");
    expect(container.querySelector(".log-body")?.textContent).toContain("line B");
  });
});
