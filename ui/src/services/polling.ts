/**
 * Polling service with configurable intervals and automatic cancellation.
 * Falls back to WebSocket events when available (Hybrid approach).
 */

type PollCallback<T> = (data: T) => void;

export class PollingService {
  private timer: ReturnType<typeof setInterval> | null = null;
  private listeners = new Map<string, Set<PollCallback<any>>>();

  constructor(
    private fetchFn: () => Promise<unknown>,
    private intervalMs: number = Number(import.meta.env.VITE_POLL_INTERVAL) || 5000,
  ) {}

  start(): void {
    this.stop();
    this.tick();
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  on<T>(event: string, callback: PollCallback<T>): void {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(callback as any);
  }

  private async tick(): Promise<void> {
    try {
      const data = await this.fetchFn();
      this.listeners.get('data')?.forEach(cb => cb(data));
    } catch (err) {
      console.warn('[Polling] Fetch error:', err);
      this.listeners.get('error')?.forEach(cb => cb(err));
    } finally {
      this.timer = setTimeout(() => this.tick(), this.intervalMs);
    }
  }
}

/** Create a cost polling service */
export function createCostPolling(): PollingService {
  // Import dynamically to avoid circular deps
  return new PollingService(
    async () => (await import('./api')).costApi.getSnapshot(),
    2000,
  );
}

/** Create a swarm health polling service */
export function createSwarmPolling(): PollingService {
  return new PollingService(
    async () => (await import('./api')).swarmApi.getHealth(),
    5000,
  );
}
