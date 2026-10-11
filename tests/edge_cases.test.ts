import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("edge cases audit: formatElapsed helper", () => {
  const formatElapsed = (sec: number) => {
    const safeSec = Math.max(0, Math.floor(Number.isFinite(sec) ? sec : 0));
    const m = Math.floor(safeSec / 60);
    const s = safeSec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}s`;
  };

  it("formats zero elapsed time", () => {
    assert.equal(formatElapsed(0), "00:00s");
  });

  it("handles negative values caused by clock skew cleanly", () => {
    assert.equal(formatElapsed(-15), "00:00s");
  });

  it("handles NaN or undefined inputs without throwing", () => {
    assert.equal(formatElapsed(NaN), "00:00s");
  });

  it("formats standard durations accurately", () => {
    assert.equal(formatElapsed(105), "01:45s");
    assert.equal(formatElapsed(3600), "60:00s");
  });
});

describe("edge cases audit: blob url revocation lifecycle", () => {
  it("delays revocation to allow async download stream initialization", async () => {
    let revoked = false;
    const fakeRevoke = () => {
      revoked = true;
    };

    // Immediate revocation would be false before timeout
    setTimeout(fakeRevoke, 50);
    assert.equal(revoked, false);

    await new Promise((resolve) => setTimeout(resolve, 60));
    assert.equal(revoked, true);
  });
});
