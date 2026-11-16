/**
 * WebSocket client for real-time backend events. Auto-reconnects with exponential backoff.
 */

import type { WsEvent } from '@/types/api';

export type WsState = 'connected' | 'disconnected' | 'reconnecting';
type Listener = (event: WsEvent) => void;

export class SwarmWebSocket {
  private ws: WebSocket | null = null;
  private reconnectDelay = 1000;
  private readonly maxReconnectDelay = 30_000;
  private manualClose = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private listeners = new Set<Listener>();
  private statusListeners = new Set<(s: WsState) => void>();
  state: WsState = 'disconnected';

  constructor(private url: string = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/events') {}

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
    this.manualClose = false;
    this.setState('reconnecting');
    const ws = new WebSocket(this.url);
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectDelay = 1000;
      this.setState('connected');
    };
    ws.onmessage = (msg) => {
      try {
        const event: WsEvent = JSON.parse(msg.data);
        this.listeners.forEach((cb) => cb(event));
      } catch (err) {
        console.error('[ws] bad message', err);
      }
    };
    ws.onclose = () => {
      if (this.ws === ws) this.ws = null;
      this.setState('disconnected');
      if (!this.manualClose) {
        this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      }
    };
    ws.onerror = () => ws.close();
  }

  disconnect(): void {
    this.manualClose = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
    this.setState('disconnected');
  }

  subscribe(cb: Listener): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  onStatus(cb: (s: WsState) => void): () => void {
    this.statusListeners.add(cb);
    cb(this.state);
    return () => this.statusListeners.delete(cb);
  }

  private setState(s: WsState): void {
    this.state = s;
    this.statusListeners.forEach((cb) => cb(s));
  }
}

export const swarmWs = new SwarmWebSocket();
