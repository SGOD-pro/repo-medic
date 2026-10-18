import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { stopProcess } from "./process_control.mjs";

describe("process control: stopProcess helper and regressions", () => {
  it("escalates to SIGKILL and awaits confirmed exit for a child that ignores SIGTERM", async () => {
    // Regression test: child explicitly traps and ignores SIGTERM.
    // The previous implementation checked proc.killed (which became true after SIGTERM),
    // skipping SIGKILL escalation and resolving prematurely before child exit.
    const child = spawn("node", [
      "-e",
      'process.on("SIGTERM", () => {}); setInterval(() => {}, 1000);',
    ]);

    await new Promise((resolve) => setTimeout(resolve, 150));
    assert.equal(child.exitCode, null, "Child process should initially be running");
    assert.equal(child.signalCode, null, "Child process should have no initial signal");

    const startTime = Date.now();
    await stopProcess(child, 300);
    const duration = Date.now() - startTime;

    // Must have waited at least timeout duration before escalation
    assert.ok(duration >= 250, `Expected duration >= 250ms, got ${duration}ms`);

    // Must be confirmed terminated with SIGKILL
    assert.ok(
      child.exitCode !== null || child.signalCode !== null,
      "Child process must be terminated"
    );
    assert.equal(child.signalCode, "SIGKILL", "Child must be killed via escalated SIGKILL");

    // Must have cleaned up event listeners
    assert.equal(
      child.listenerCount("exit"),
      0,
      "Exit listener must be removed on completion"
    );
  });

  it("terminates a standard child with SIGTERM promptly without waiting for timeout", async () => {
    const child = spawn("node", ["-e", "setInterval(() => {}, 1000);"]);

    await new Promise((resolve) => setTimeout(resolve, 150));
    assert.equal(child.exitCode, null);

    const startTime = Date.now();
    await stopProcess(child, 5000);
    const duration = Date.now() - startTime;

    // Prompt exit should take much less than the 5000ms escalation timeout
    assert.ok(duration < 2000, `Expected prompt exit (< 2000ms), took ${duration}ms`);
    assert.ok(
      child.exitCode !== null || child.signalCode !== null,
      "Child process must be terminated"
    );
    assert.equal(child.signalCode, "SIGTERM", "Child should terminate from SIGTERM");
    assert.equal(child.listenerCount("exit"), 0, "Exit listener must be removed");
  });

  it("handles an already exited child process idempotently without hanging", async () => {
    const child = spawn("node", ["-e", "process.exit(0);"]);

    await new Promise((resolve) => child.once("exit", resolve));
    assert.equal(child.exitCode, 0, "Child should have already exited with code 0");

    const startTime = Date.now();
    await stopProcess(child, 5000);
    await stopProcess(child, 5000);
    const duration = Date.now() - startTime;

    assert.ok(duration < 100, `Expected immediate return (< 100ms), took ${duration}ms`);
  });

  it("resolves via hard ceiling safety timeout if process fails to exit after SIGKILL", async () => {
    const mockChild = Object.assign(new EventEmitter(), {
      pid: 99999,
      exitCode: null,
      signalCode: null,
      kill: () => true,
    }) as unknown as import("node:child_process").ChildProcess;

    const startTime = Date.now();
    await stopProcess(mockChild, 50, 100);
    const duration = Date.now() - startTime;

    // Must have waited through both initial timeout and hard ceiling
    assert.ok(duration >= 130, `Expected duration >= 130ms, got ${duration}ms`);
    assert.equal(mockChild.listenerCount("exit"), 0, "Exit listener must be cleaned up on hard ceiling");
  });

  it("resolves immediately when kill throws ESRCH indicating process is already gone", async () => {
    const mockChild = Object.assign(new EventEmitter(), {
      pid: 99998,
      exitCode: null,
      signalCode: null,
      kill: () => {
        const err = new Error("kill ESRCH") as NodeJS.ErrnoException;
        err.code = "ESRCH";
        throw err;
      },
    }) as unknown as import("node:child_process").ChildProcess;

    const startTime = Date.now();
    await stopProcess(mockChild, 5000, 5000);
    const duration = Date.now() - startTime;

    assert.ok(duration < 100, `Expected immediate resolution (< 100ms), took ${duration}ms`);
    assert.equal(mockChild.listenerCount("exit"), 0, "Exit listener must be removed");
  });

  it("terminates a detached child process group cleanly", async () => {
    if (process.platform === "win32") return;

    const child = spawn("node", ["-e", "setInterval(() => {}, 1000);"], {
      detached: true,
    });

    await new Promise((resolve) => setTimeout(resolve, 150));
    assert.equal(child.exitCode, null);

    await stopProcess(child, 1000);
    assert.ok(
      child.exitCode !== null || child.signalCode !== null,
      "Detached child process must be terminated"
    );
    assert.equal(child.listenerCount("exit"), 0, "Exit listener must be removed");
  });

  it("handles null or undefined process arguments safely", async () => {
    // Should not throw and should resolve immediately
    await stopProcess(null);
    await stopProcess(undefined);
  });
});

