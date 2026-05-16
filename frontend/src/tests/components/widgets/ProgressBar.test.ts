import { describe, it, expect } from "vitest";
import { render } from "@testing-library/svelte";
import ProgressBar from "$lib/components/widgets/ProgressBar.svelte";

describe("ProgressBar", () => {
  it("renders nothing when inactive", () => {
    const { container } = render(ProgressBar, { props: { active: false } });
    expect(container.querySelector(".track")).toBeNull();
  });

  it("renders track when active", () => {
    const { container } = render(ProgressBar, { props: { active: true } });
    expect(container.querySelector(".track")).toBeInTheDocument();
  });

  it("shows shimmer bar when progress is null (indeterminate)", () => {
    const { container } = render(ProgressBar, { props: { active: true, progress: null } });
    expect(container.querySelector(".bar.shimmer")).toBeInTheDocument();
  });

  it("shows deterministic bar with correct width at 60%", () => {
    const { container } = render(ProgressBar, { props: { active: true, progress: 0.6 } });
    const bar = container.querySelector(".bar") as HTMLElement;
    expect(bar).not.toHaveClass("shimmer");
    expect(bar.style.width).toBe("60%");
  });

  it("shows 0% width for progress=0", () => {
    const { container } = render(ProgressBar, { props: { active: true, progress: 0 } });
    const bar = container.querySelector(".bar") as HTMLElement;
    expect(bar.style.width).toBe("0%");
  });

  it("shows 100% width for progress=1", () => {
    const { container } = render(ProgressBar, { props: { active: true, progress: 1 } });
    const bar = container.querySelector(".bar") as HTMLElement;
    expect(bar.style.width).toBe("100%");
  });
});
