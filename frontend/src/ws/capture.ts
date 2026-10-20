import { refreshSession } from '../api/client';
import { useAuth } from '../stores/auth';

export type CaptureState =
  | 'idle'
  | 'connecting'
  | 'streaming'
  | 'reconnecting'
  | 'stopped'
  | 'error';

export type ZoneResult = {
  type: 'zone_result';
  zone_id: string;
  zone_code: string;
  status: 'unclassified' | 'safe' | 'caution' | 'unsafe' | 'blocked';
  analysable: boolean;
  risk_score: number;
  confidence: number;
  reasons: { key: string; params: Record<string, unknown> }[];
  frame_url: string | null;
  overlay_url: string | null;
  latency_ms: number;
};

export type CaptureAlert = {
  type: 'alert';
  severity: 'crit' | 'warn' | 'info';
  alert_type: string;
  message_key: string;
  params: Record<string, string>;
};

type Handlers = {
  onState: (s: CaptureState, detail?: string) => void;
  onResult: (r: ZoneResult) => void;
  onAlert: (a: CaptureAlert) => void;
  onFrameError: (code: string) => void;
  grab: () => Promise<Blob | null>;
};

const MAX_IN_FLIGHT = 2;

/**
 * Streams camera frames to /ws/capture (HANDOFF §7.3). Sends at the server's target_fps, never
 * builds a backlog (skips a tick while the socket is busy), and transparently starts a new
 * session after a dropped connection while capture is on (SRS §5.2.2).
 */
export class CaptureClient {
  private ws: WebSocket | null = null;
  private timer: number | undefined;
  private retry: number | undefined;
  private running = false;
  private attempt = 0;
  private inFlight = 0;

  private h: Handlers;

  constructor(
    private zoneId: string,
    handlers: Handlers,
  ) {
    // A failing UI callback (e.g. speech) must never stop the capture loop.
    const guard =
      <A extends unknown[]>(fn: (...a: A) => void) =>
      (...a: A) => {
        try {
          fn(...a);
        } catch (e) {
          console.error('capture handler failed', e);
        }
      };
    this.h = {
      grab: handlers.grab,
      onState: guard(handlers.onState),
      onResult: guard(handlers.onResult),
      onAlert: guard(handlers.onAlert),
      onFrameError: guard(handlers.onFrameError),
    };
  }

  start(): void {
    this.running = true;
    this.connect();
  }

  stop(): void {
    this.running = false;
    window.clearInterval(this.timer);
    window.clearTimeout(this.retry);
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: 'stop' }));
    this.ws?.close(1000);
    this.ws = null;
    this.h.onState('stopped');
  }

  private connect(): void {
    this.h.onState(this.attempt ? 'reconnecting' : 'connecting');
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/capture`);
    ws.binaryType = 'arraybuffer';
    this.ws = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', token: useAuth.getState().accessToken }));
      ws.send(JSON.stringify({ type: 'start', zone_id: this.zoneId }));
    };
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data as string);
      switch (msg.type) {
        case 'started':
          this.attempt = 0;
          this.inFlight = 0;
          this.loop(Number(msg.target_fps) || 1);
          this.h.onState('streaming', String(msg.target_fps));
          break;
        case 'zone_result':
          this.inFlight = Math.max(0, this.inFlight - 1);
          this.h.onResult(msg as ZoneResult);
          break;
        case 'alert':
          this.h.onAlert(msg as CaptureAlert);
          break;
        case 'error':
          if (['not_jpeg', 'frame_too_large', 'undecodable_frame'].includes(msg.code)) {
            this.inFlight = Math.max(0, this.inFlight - 1);
            this.h.onFrameError(msg.code);
          } else {
            this.h.onState('error', msg.code);
          }
          break;
        case 'ping':
          ws.send(JSON.stringify({ type: 'pong' }));
          break;
      }
    };
    ws.onclose = async (e) => {
      window.clearInterval(this.timer);
      if (!this.running || this.ws !== ws) return;
      if (e.code === 4403 || e.code === 4400) {
        this.running = false;
        this.h.onState('error', e.reason || 'zone_not_capturable');
        return;
      }
      if (e.code === 4401) await refreshSession();
      const delay = Math.min(10_000, 800 * 2 ** this.attempt);
      this.attempt++;
      this.h.onState('reconnecting');
      this.retry = window.setTimeout(() => this.running && this.connect(), delay);
    };
  }

  private loop(fps: number): void {
    window.clearInterval(this.timer);
    this.timer = window.setInterval(async () => {
      const ws = this.ws;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      if (ws.bufferedAmount > 0 || this.inFlight >= MAX_IN_FLIGHT) return; // never queue
      const blob = await this.h.grab();
      if (!blob || ws.readyState !== WebSocket.OPEN) return;
      this.inFlight++;
      ws.send(await blob.arrayBuffer());
    }, 1000 / fps);
  }
}
