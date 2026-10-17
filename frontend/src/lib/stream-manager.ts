import {
  EventEnvelope,
  ConnectionStatus,
  ErrorDetail,
} from "./contracts";

export interface StreamManagerOptions {
  runId: string;
  streamFetcher: (lastEventId: string | null) => AsyncIterable<EventEnvelope> | Promise<AsyncIterable<EventEnvelope>>;
  onEvent: (event: EventEnvelope) => void;
  onStatusChange: (status: ConnectionStatus, attempt: number) => void;
  onError?: (error: ErrorDetail) => void;
  maxRetries?: number;
  backoffIntervals?: number[];
}

export class StreamManager {
  private runId: string;
  private streamFetcher: (lastEventId: string | null) => AsyncIterable<EventEnvelope> | Promise<AsyncIterable<EventEnvelope>>;
  private onEvent: (event: EventEnvelope) => void;
  private onStatusChange: (status: ConnectionStatus, attempt: number) => void;
  private onError?: (error: ErrorDetail) => void;

  private status: ConnectionStatus = "disconnected";
  private attempt: number = 0;
  private maxRetries: number;
  private backoffIntervals: number[];
  private lastEventId: string | null = null;
  private isCancelled: boolean = false;
  private retryTimer: NodeJS.Timeout | null = null;

  constructor(options: StreamManagerOptions) {
    this.runId = options.runId;
    this.streamFetcher = options.streamFetcher;
    this.onEvent = options.onEvent;
    this.onStatusChange = options.onStatusChange;
    this.onError = options.onError;

    this.maxRetries = options.maxRetries ?? 5;
    this.backoffIntervals = options.backoffIntervals ?? [1000, 2000, 4000, 8000, 10000];
  }

  public getStatus(): ConnectionStatus {
    return this.status;
  }

  public getAttempt(): number {
    return this.attempt;
  }

  public getLastEventId(): string | null {
    return this.lastEventId;
  }

  public start(): void {
    this.isCancelled = false;
    this.attempt = 0;
    this.setStatus("connected", 0);
    this.consumeStream();
  }

  public stop(): void {
    this.isCancelled = true;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.setStatus("disconnected", 0);
  }

  public retryManual(): void {
    if (this.isCancelled) {
      this.isCancelled = false;
    }
    this.attempt = 0;
    this.setStatus("reconnecting", 1);
    this.consumeStream();
  }

  public simulateDisconnect(): void {
    if (this.status === "disconnected") return;
    this.handleStreamError(new Error("Simulated network stream interruption"));
  }

  public simulateError(code: string, message: string, traceback?: string): void {
    const errorDetail: ErrorDetail = {
      code,
      message,
      traceback: traceback || null,
      timestamp: new Date().toISOString(),
      recoverable: false,
    };
    if (this.onError) {
      this.onError(errorDetail);
    }
  }

  private setStatus(status: ConnectionStatus, attempt: number) {
    this.status = status;
    this.attempt = attempt;
    this.onStatusChange(status, attempt);
  }

  private async consumeStream(): Promise<void> {
    try {
      const stream = await this.streamFetcher(this.lastEventId);
      this.setStatus("connected", 0);
      this.attempt = 0;

      for await (const event of stream) {
        if (this.isCancelled) break;

        this.lastEventId = String(event.seq);
        this.onEvent(event);

        if (event.type === "run.finished" || event.type === "run.cancelled") {
          this.stop();
          return;
        }

        if (event.type === "run.error") {
          const payload = event.payload as unknown as ErrorDetail;
          if (this.onError) {
            this.onError({
              code: payload?.code || "ENGINE_ERROR",
              message: payload?.message || "Execution encountered an unrecoverable engine failure",
              traceback: payload?.traceback || null,
              timestamp: event.ts || new Date().toISOString(),
              recoverable: false,
            });
          }
        }
      }
    } catch (err) {
      if (this.isCancelled) return;
      this.handleStreamError(err);
    }
  }

  private handleStreamError(err: unknown): void {
    if (this.isCancelled) return;

    if (this.attempt >= this.maxRetries) {
      this.setStatus("disconnected", this.attempt);
      if (this.onError) {
        this.onError({
          code: "CONNECTION_CEILING_REACHED",
          message: "Unable to reconnect to execution stream after 5 attempts.",
          traceback: String(err),
          timestamp: new Date().toISOString(),
          recoverable: true,
        });
      }
      return;
    }

    const nextAttempt = this.attempt + 1;
    this.setStatus("reconnecting", nextAttempt);

    const delay = this.backoffIntervals[Math.min(nextAttempt - 1, this.backoffIntervals.length - 1)];

    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      if (!this.isCancelled) {
        this.consumeStream();
      }
    }, delay);
  }
}
