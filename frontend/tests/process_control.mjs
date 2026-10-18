/**
 * Process lifecycle management utilities for integration and acceptance tests.
 */

/**
 * Process lifecycle management utilities for integration and acceptance tests.
 */

/**
 * Sends a signal to a child process, attempting process group signaling first
 * if detached, and falling back to process level signaling.
 *
 * @param {import("node:child_process").ChildProcess} proc
 * @param {NodeJS.Signals | number} signal
 */
function sendSignal(proc, signal) {
  if (process.platform !== "win32" && proc.pid) {
    try {
      process.kill(-proc.pid, signal);
      return;
    } catch {
      // Process group signaling failed or proc is not a process group leader; fall through
    }
  }
  proc.kill(signal);
}

/**
 * Gracefully terminates a child process using SIGTERM, escalating to SIGKILL
 * if the process does not terminate within the specified timeout, with a hard
 * ceiling timeout to ensure test harness promises never hang indefinitely.
 * Determines termination from exitCode/signalCode or exit events, not ChildProcess.killed.
 *
 * @param {import("node:child_process").ChildProcess | null | undefined} proc - The child process to terminate
 * @param {number} [timeoutMs=3000] - Duration in ms before escalating to SIGKILL
 * @param {number} [hardCeilingMs=2000] - Safety ceiling duration after SIGKILL before forcing promise resolution
 * @returns {Promise<void>}
 */
export async function stopProcess(proc, timeoutMs = 3000, hardCeilingMs = 2000) {
  if (!proc) return;
  if (proc.exitCode !== null || proc.signalCode !== null) return;

  await new Promise((resolve) => {
    let timer = null;
    let ceilingTimer = null;
    let onExit = null;

    const cleanup = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      if (ceilingTimer) {
        clearTimeout(ceilingTimer);
        ceilingTimer = null;
      }
      if (onExit) {
        proc.removeListener("exit", onExit);
        onExit = null;
      }
    };

    onExit = () => {
      cleanup();
      resolve();
    };

    proc.once("exit", onExit);

    if (proc.exitCode !== null || proc.signalCode !== null) {
      cleanup();
      resolve();
      return;
    }

    try {
      sendSignal(proc, "SIGTERM");
    } catch (err) {
      if (err?.code === "ESRCH" || proc.exitCode !== null || proc.signalCode !== null) {
        cleanup();
        resolve();
        return;
      }
    }

    timer = setTimeout(() => {
      timer = null;
      if (proc.exitCode !== null || proc.signalCode !== null) {
        cleanup();
        resolve();
        return;
      }

      try {
        sendSignal(proc, "SIGKILL");
      } catch (err) {
        if (err?.code === "ESRCH" || proc.exitCode !== null || proc.signalCode !== null) {
          cleanup();
          resolve();
          return;
        }
      }

      ceilingTimer = setTimeout(() => {
        ceilingTimer = null;
        if (proc.exitCode === null && proc.signalCode === null) {
          cleanup();
          console.warn(
            `[stopProcess] Warning: Process ${proc.pid} did not exit after SIGKILL and hard ceiling timeout of ${hardCeilingMs}ms.`
          );
          resolve();
        }
      }, hardCeilingMs);
    }, timeoutMs);
  });
}

