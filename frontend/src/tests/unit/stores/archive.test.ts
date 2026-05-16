import { describe, it, expect } from "vitest";
import { get } from "svelte/store";
import { pendingArchivePath } from "$lib/stores/archive";

describe("pendingArchivePath", () => {
  it("starts as null", () => {
    expect(get(pendingArchivePath)).toBeNull();
  });

  it("can be set to a path string", () => {
    pendingArchivePath.set("/home/user/archive.zip");
    expect(get(pendingArchivePath)).toBe("/home/user/archive.zip");
  });

  it("can be reset to null", () => {
    pendingArchivePath.set("/some/path.zip");
    pendingArchivePath.set(null);
    expect(get(pendingArchivePath)).toBeNull();
  });
});
