import { refreshSession } from '../api/client';
import { useAuth } from '../stores/auth';

export type SocketState = 'connecting' | 'open' | 'lost' | 'closed';
type Handlers = {
  onMessage: (msg: { type: string; [k: string]: unknown }) => void;
  onState: (s: SocketState) => void;
};

const MAX_BACKOFF_MS = 15_000;
const SILENCE_MS = 60_000; // server pings every 25 s

/**
 * Reconnecting WebSocket: authenticates with the access token as the first message
 * (HANDOFF §7.2), backs off exponentially with jitter, refreshes the token on 4401.
 */
export class LiveSocket {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private timer: number | undefined;
  private watchdog: number | undefined;
  private stopped = false;

  constructor(
    private path: string,
    private h: Handlers,
  ) {}

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    window.clearTimeout(this.timer);
    window.clearTimeout(this.watchdog);
    this.ws?.close(1000);
    this.ws = null;
    this.h.onState('closed');
  }

  private url(): string {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${location.host}${this.path}`;
  }

  private kick(): void {
    window.clearTimeout(this.watchdog);
    this.watchdog = window.setTimeout(() => this.ws?.close(4000), SILENCE_MS);
  }

  private connect(): void {
    this.h.onState(this.attempt === 0 ? 'connecting' : 'lost');
    const ws = new WebSocket(this.url());
    this.ws = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', token: useAuth.getState().accessToken }));
      this.kick();
    };
    ws.onmessage = (e) => {
      this.kick();
      let msg: { type: string; [k: string]: unknown };
      try {
        msg = JSON.parse(e.data as string);
      } catch {
        return;
      }
      if (msg.type === 'ready') {
        this.attempt = 0;
        this.h.onState('open');
      }
      if (msg.type === 'ping') ws.send(JSON.stringify({ type: 'pong' }));
      this.h.onMessage(msg);
    };
    ws.onclose = async (e) => {
      window.clearTimeout(this.watchdog);
      if (this.stopped || this.ws !== ws) return;
      if (e.code === 4403 || e.code === 4404) {
        this.h.onState('closed');
        return; // not retryable
      }
      if (e.code === 4401 && !(await refreshSession())) {
        this.h.onState('closed');
        return;
      }
      this.h.onState('lost');
      const delay =
        Math.min(MAX_BACKOFF_MS, 1000 * 2 ** this.attempt) * (0.7 + Math.random() * 0.6);
      this.attempt++;
      this.timer = window.setTimeout(() => this.connect(), delay);
    };
  }
}
