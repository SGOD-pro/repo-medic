import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { StreamManager } from "../src/lib/stream-manager";
import { MockTransport } from "../src/lib/api";
import { EventEnvelope, ConnectionStatus, ErrorDetail } from "../src/lib/contracts";

describe("stream manager and resilience (AC-1..AC-8)", () => {
  it("consumes stream events and updates lastEventId (covers: AC-3, AC-4)", async () => {
    const receivedEvents: EventEnvelope[] = [];
    const statusHistory: ConnectionStatus[] = [];

    async function* testStream(): AsyncIterable<EventEnvelope> {
      yield {
        run_id: "run-test-1",
        seq: 1,
        ts: new Date().toISOString(),
        type: "run.started",
        payload: { mode: "live" },
      };
      yield {
        run_id: "run-test-1",
        seq: 2,
        ts: new Date().toISOString(),
        type: "stage.completed",
        payload: { stage: "baseline", passed: true },
      };
    }

    const manager = new StreamManager({
      runId: "run-test-1",
      streamFetcher: () => testStream(),
      onEvent: (event) => receivedEvents.push(event),
      onStatusChange: (status) => statusHistory.push(status),
    });

    manager.start();

    // Allow async iterable processing
    await new Promise((res) => setTimeout(res, 50));

    assert.equal(receivedEvents.length, 2);
    assert.equal(manager.getLastEventId(), "2");
    assert.equal(manager.getStatus(), "connected");
  });

  it("stops stream consumption when run.cancelled or run.finished event is received (covers: AC-2)", async () => {
    const receivedEvents: EventEnvelope[] = [];

    async function* cancelStream(): AsyncIterable<EventEnvelope> {
      yield {
        run_id: "run-test-2",
        seq: 1,
        ts: new Date().toISOString(),
        type: "run.started",
        payload: {},
      };
      yield {
        run_id: "run-test-2",
        seq: 2,
        ts: new Date().toISOString(),
        type: "run.cancelled",
        payload: { reason: "User cancelled" },
      };
      // Should not process event 3
      yield {
        run_id: "run-test-2",
        seq: 3,
        ts: new Date().toISOString(),
        type: "stage.completed",
        payload: {},
      };
    }

    const manager = new StreamManager({
      runId: "run-test-2",
      streamFetcher: () => cancelStream(),
      onEvent: (event) => receivedEvents.push(event),
      onStatusChange: () => {},
    });

    manager.start();
    await new Promise((res) => setTimeout(res, 50));

    assert.equal(receivedEvents.length, 2);
    assert.equal(manager.getStatus(), "disconnected");
  });

  it("initiates exponential backoff on stream interruption with custom intervals (covers: AC-3)", async () => {
    let fetchCount = 0;
    const statusChanges: { status: ConnectionStatus; attempt: number }[] = [];

    const manager = new StreamManager({
      runId: "run-test-3",
      maxRetries: 3,
      backoffIntervals: [20, 40, 80],
      streamFetcher: () => {
        fetchCount++;
        if (fetchCount === 1) {
          throw new Error("Temporary network drop");
        }
        async function* recoveredStream(): AsyncIterable<EventEnvelope> {
          yield {
            run_id: "run-test-3",
            seq: 10,
            ts: new Date().toISOString(),
            type: "stage.completed",
            payload: {},
          };
        }
        return recoveredStream();
      },
      onEvent: () => {},
      onStatusChange: (status, attempt) => statusChanges.push({ status, attempt }),
    });

    manager.start();
    // Allow first error and backoff timer (20ms) to fire
    await new Promise((res) => setTimeout(res, 80));

    assert.ok(fetchCount >= 2, "Stream fetcher should have retried");
    const reconnecting = statusChanges.filter((s) => s.status === "reconnecting");
    assert.ok(reconnecting.length >= 1, "Should enter reconnecting state");
    assert.equal(reconnecting[0].attempt, 1);
    assert.equal(manager.getStatus(), "connected");
  });

  it("passes Last-Event-ID on reconnection to resume without duplicates (covers: AC-4)", async () => {
    let capturedLastEventId: string | null = "uninitialized";
    let attempts = 0;

    const manager = new StreamManager({
      runId: "run-test-4",
      maxRetries: 2,
      backoffIntervals: [20, 40],
      streamFetcher: (lastEventId) => {
        attempts++;
        capturedLastEventId = lastEventId;
        if (attempts === 1) {
          async function* initialStream(): AsyncIterable<EventEnvelope> {
            yield {
              run_id: "run-test-4",
              seq: 5,
              ts: new Date().toISOString(),
              type: "stage.completed",
              payload: {},
            };
            throw new Error("Socket disconnected unexpectedly");
          }
          return initialStream();
        }
        async function* resumedStream(): AsyncIterable<EventEnvelope> {
          yield {
            run_id: "run-test-4",
            seq: 6,
            ts: new Date().toISOString(),
            type: "candidate.completed",
            payload: {},
          };
        }
        return resumedStream();
      },
      onEvent: () => {},
      onStatusChange: () => {},
    });

    manager.start();
    await new Promise((res) => setTimeout(res, 80));

    assert.equal(capturedLastEventId, "5", "Second fetch must pass lastEventId=5");
    assert.equal(manager.getLastEventId(), "6");
  });

  it("transitions to disconnected when retry ceiling is exceeded (covers: AC-5)", async () => {
    let emittedError: ErrorDetail | null = null;
    const manager = new StreamManager({
      runId: "run-test-5",
      maxRetries: 2,
      backoffIntervals: [10, 10],
      streamFetcher: () => {
        throw new Error("Persistent backend outage");
      },
      onEvent: () => {},
      onStatusChange: () => {},
      onError: (err) => {
        emittedError = err;
      },
    });

    manager.start();
    await new Promise((res) => setTimeout(res, 80));

    assert.equal(manager.getStatus(), "disconnected");
    assert.ok(emittedError !== null);
    assert.equal((emittedError as ErrorDetail).code, "CONNECTION_CEILING_REACHED");
    assert.equal((emittedError as ErrorDetail).recoverable, true);
  });

  it("manual retry resets state and attempts reconnection (covers: AC-5)", async () => {
    let allowSuccess = false;
    let callCount = 0;

    const manager = new StreamManager({
      runId: "run-test-6",
      maxRetries: 1,
      backoffIntervals: [10],
      streamFetcher: () => {
        callCount++;
        if (!allowSuccess) {
          throw new Error("Initial failure");
        }
        async function* successStream(): AsyncIterable<EventEnvelope> {
          yield {
            run_id: "run-test-6",
            seq: 1,
            ts: new Date().toISOString(),
            type: "run.started",
            payload: {},
          };
        }
        return successStream();
      },
      onEvent: () => {},
      onStatusChange: () => {},
    });

    manager.start();
    await new Promise((res) => setTimeout(res, 50));
    assert.equal(manager.getStatus(), "disconnected");

    // Enable success and trigger manual retry
    allowSuccess = true;
    manager.retryManual();
    await new Promise((res) => setTimeout(res, 50));

    assert.equal(manager.getStatus(), "connected");
    assert.ok(callCount >= 2);
  });

  it("handles structured error events and offline simulation (covers: AC-6, AC-8)", async () => {
    let reportedError: ErrorDetail | null = null;

    const manager = new StreamManager({
      runId: "run-test-7",
      streamFetcher: () => {
        async function* errStream(): AsyncIterable<EventEnvelope> {
          yield {
            run_id: "run-test-7",
            seq: 1,
            ts: new Date().toISOString(),
            type: "run.error",
            payload: {
              code: "SANDBOX_TIMEOUT",
              message: "Execution timed out after 120s",
              traceback: "TimeoutError at sandbox.py:110",
              recoverable: false,
            },
          };
        }
        return errStream();
      },
      onEvent: () => {},
      onStatusChange: () => {},
      onError: (err) => {
        reportedError = err;
      },
    });

    manager.start();
    await new Promise((res) => setTimeout(res, 50));

    assert.ok(reportedError !== null);
    assert.equal((reportedError as ErrorDetail).code, "SANDBOX_TIMEOUT");
    assert.equal((reportedError as ErrorDetail).message, "Execution timed out after 120s");
    assert.equal((reportedError as ErrorDetail).traceback, "TimeoutError at sandbox.py:110");

    // Test simulateError method
    let simulatedError: ErrorDetail | null = null;
    manager["onError"] = (err) => {
      simulatedError = err;
    };
    manager.simulateError("SYNTHETIC_FAULT", "Offline testing fault", "Traceback line 42");
    assert.ok(simulatedError !== null);
    assert.equal((simulatedError as ErrorDetail).code, "SYNTHETIC_FAULT");
  });

  it("MockTransport filters events when lastEventId is provided (covers: AC-4, AC-8)", async () => {
    const transport = new MockTransport();
    const allEvents = await transport.getRunEvents("run-123");
    assert.equal(allEvents.length, 6);

    const filteredEvents = await transport.getRunEvents("run-123", "3");
    assert.equal(filteredEvents.length, 3);
    assert.equal(filteredEvents[0].seq, 4);
    assert.equal(filteredEvents[1].seq, 5);
    assert.equal(filteredEvents[2].seq, 6);
  });
});
