import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { cn } from "../src/lib/utils";

describe("utils: cn class merge helper", () => {
  it("merges static class names", () => {
    assert.equal(cn("foo", "bar"), "foo bar");
  });

  it("handles falsy values, null, and undefined cleanly", () => {
    assert.equal(cn("foo", null, undefined, false, "bar"), "foo bar");
  });

  it("handles conditional class expressions", () => {
    const isTrue = true;
    const isFalse = false;
    assert.equal(cn("base", isTrue && "active", isFalse && "disabled"), "base active");
  });

  it("resolves empty input to empty string", () => {
    assert.equal(cn(), "");
  });
});
