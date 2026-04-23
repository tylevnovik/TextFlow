import { describe, expect, it } from "vitest";

describe("workspace store test harness", () => {
  it("loads the reducer module", async () => {
    const mod = await import("./workspaceStore");
    expect(mod).toBeTruthy();
  });
});
