/**
 * WebSocket service for real-time agent swarm updates.
 * Auto-reconnects on disconnect with exponential backoff.
 */

import type { WsEvent, PipelineUpdatePayload, AgentStatusChangePayload } from '@/types/api';

type EventCallback<T> = (event: T) => void;

export class SwarmWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30_000;
  private isManualClose = false;
  private eventListeners = new Map<string, Set<EventCallback<any>>>();
  private statusListeners = new Set<((state: 'connected' | 'disconnected' | 'reconnecting') => void)>();

  constructor(
    url: string = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/events',
  ) {
    this.url = url;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.isManualClose = false;
    this.emitStatus('reconnecting');

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000; // reset on successful connect
      this.emitStatus('connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const wsEvent: WsEvent = JSON.parse(event.data);
        this.dispatch(wsEvent.type, wsEvent);
        this.dispatch('all', wsEvent); // broadcast to wildcard listeners
      } catch (err) {
        console.error('[SwarmWS] Failed to parse message:', err);
      }
    };

    this.ws.onclose = () => {
      this.emitStatus('disconnected');
      if (!this.isManualClose) {
        setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      }
    };

    this.ws.onerror = () => {
      // onerror is always followed by close in WebSocket spec
    };
  }

  /** Subscribe to a specific event type */
  on<T extends WsEvent['type']>(event: T, callback: EventCallback<Extract<WsEvent, { type: T }>['payload']>): void;
  on(event: 'all', callback: EventCallback<WsEvent>): void;
  on(event: string, callback: EventCallback<any>): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event)!.add(callback);
  }

  /** Unsubscribe from an event */
  off(event: string, callback: EventCallback<any>): void {
    this.eventListeners.get(event)?.delete(callback);
  }

  onStatus(callback: (state: 'connected' | 'disconnected' | 'reconnecting') => void): void {
    this.statusListeners.add(callback);
    // Emit current status
    if (this.ws?.readyState === WebSocket.OPEN) callback('connected');
    else if (this.ws) callback('reconnecting');
    else callback('disconnected');
  }

  private dispatch(eventType: string, event: WsEvent): void {
    this.eventListeners.get(eventType)?.forEach(cb => cb(event.payload));
  }

  private emitStatus(state: 'connected' | 'disconnected' | 'reconnecting'): void {
    this.statusListeners.forEach(cb => cb(state));
  }

  /** Send a command to the backend */
  send(command: string, data?: Record<string, any>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ command, data, ts: Date.now() }));
    }
  }

  disconnect(): void {
    this.isManualClose = true;
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Singleton instance
export const swarmWs = new SwarmWebSocket();
