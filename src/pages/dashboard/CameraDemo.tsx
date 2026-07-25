import { useEffect, useRef, useState } from 'react';
import type { ObjectDetection, DetectedObject } from '@tensorflow-models/coco-ssd';
import './CameraDemo.css';

type ZoneStatus = 'neutral' | 'safe' | 'caution' | 'unsafe';

interface DemoZone {
  id: string;
  status: ZoneStatus;
}

interface LogEntry {
  id: number;
  text: string;
  time: string;
}

const STATUS_ORDER: ZoneStatus[] = ['neutral', 'safe', 'caution', 'unsafe'];

function initialZones(): DemoZone[] {
  return Array.from({ length: 8 }, (_, i) => ({ id: `Z${i + 1}`, status: 'neutral' }));
}

let logSeq = 0;

export function CameraDemo() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const thermalCanvasRef = useRef<HTMLCanvasElement>(null);
  const boxCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const modelRef = useRef<ObjectDetection | null>(null);
  const lastPeopleRef = useRef<DetectedObject[]>([]);
  const runningRef = useRef(false);
  const thermalRafRef = useRef<number | null>(null);
  const detectRafRef = useRef<number | null>(null);
  const detectionsTotalRef = useRef(0);

  const [demoZones, setDemoZones] = useState<DemoZone[]>(initialZones);
  const [started, setStarted] = useState(false);
  const [starting, setStarting] = useState(false);
  const [statusText, setStatusText] = useState('Camera not started. Click "Start camera" and allow browser permission when prompted.');
  const [statusColor, setStatusColor] = useState('var(--text-low)');
  const [errorBlock, setErrorBlock] = useState<'file' | 'permission' | null>(null);
  const [modelStatus, setModelStatus] = useState('Model not loaded');
  const [zoneLabel, setZoneLabel] = useState('ZONE STATUS: —');
  const [zoneColor, setZoneColor] = useState('var(--text-hi)');
  const [humanCount, setHumanCount] = useState(0);
  const [people, setPeople] = useState<DetectedObject[]>([]);
  const [log, setLog] = useState<LogEntry[]>([]);

  useEffect(() => {
    return () => {
      runningRef.current = false;
      if (thermalRafRef.current) cancelAnimationFrame(thermalRafRef.current);
      if (detectRafRef.current) cancelAnimationFrame(detectRafRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function addLog(text: string) {
    logSeq += 1;
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    setLog((l) => [{ id: logSeq, text, time }, ...l].slice(0, 8));
  }

  function addZone() {
    setDemoZones((z) => [...z, { id: `Z${z.length + 1}`, status: 'neutral' }]);
  }

  function resetMap() {
    setDemoZones((z) => z.map((zone) => ({ ...zone, status: 'neutral' })));
  }

  function cycleZone(idx: number) {
    setDemoZones((zones) =>
      zones.map((z, i) => {
        if (i !== idx) return z;
        const next = STATUS_ORDER[(STATUS_ORDER.indexOf(z.status) + 1) % STATUS_ORDER.length];
        return { ...z, status: next };
      }),
    );
  }

  function thermalLoop() {
    if (!runningRef.current) return;
    const video = videoRef.current;
    const canvas = thermalCanvasRef.current;
    if (video && canvas && video.videoWidth) {
      canvas.width = video.clientWidth;
      canvas.height = video.clientHeight;
      const ctx = canvas.getContext('2d')!;
      ctx.filter = 'grayscale(1) contrast(1.3) brightness(1.05)';
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      ctx.filter = 'none';
      const frame = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = frame.data;
      for (let i = 0; i < d.length; i += 4) {
        const v = d[i];
        let r: number, g: number, b: number;
        if (v < 64) {
          r = 0;
          g = 0;
          b = 80 + v * 2;
        } else if (v < 128) {
          r = 0;
          g = (v - 64) * 3;
          b = 180 - (v - 64) * 2;
        } else if (v < 192) {
          r = (v - 128) * 4;
          g = 180 + (v - 128);
          b = 40;
        } else {
          r = 255;
          g = 255 - (v - 192) * 4;
          b = 0;
        }
        d[i] = r;
        d[i + 1] = g;
        d[i + 2] = b;
      }
      ctx.putImageData(frame, 0, 0);

      if (lastPeopleRef.current.length) {
        const scaleX = canvas.width / video.videoWidth;
        const scaleY = canvas.height / video.videoHeight;
        ctx.strokeStyle = '#FFD23F';
        ctx.lineWidth = 2;
        ctx.font = '10px IBM Plex Mono, monospace';
        ctx.fillStyle = '#FFD23F';
        lastPeopleRef.current.forEach((p) => {
          const [x, y, w, h] = p.bbox;
          const bx = x * scaleX;
          const by = y * scaleY;
          const bw = w * scaleX;
          const bh = h * scaleY;
          ctx.strokeRect(bx, by, bw, bh);
          ctx.fillText(`HUMAN ${Math.round(p.score * 100)}%`, bx, by > 12 ? by - 4 : by + 12);
        });
      }
    }
    thermalRafRef.current = requestAnimationFrame(thermalLoop);
  }

  async function detectionLoop() {
    if (!runningRef.current) return;
    const video = videoRef.current;
    const boxCanvas = boxCanvasRef.current;
    const model = modelRef.current;

    if (video && boxCanvas && video.videoWidth && model) {
      boxCanvas.width = video.clientWidth;
      boxCanvas.height = video.clientHeight;
      try {
        const preds = await model.detect(video);
        const detected = preds.filter((p) => p.class === 'person' && p.score > 0.55);
        lastPeopleRef.current = detected;
        setPeople(detected);

        const scaleX = boxCanvas.width / video.videoWidth;
        const scaleY = boxCanvas.height / video.videoHeight;
        const ctx = boxCanvas.getContext('2d')!;
        ctx.clearRect(0, 0, boxCanvas.width, boxCanvas.height);

        let status: string;
        let color: string;
        if (detected.length === 0) {
          status = 'SAFE';
          color = '47,166,110';
        } else if (detected.length === 1) {
          status = 'CAUTION';
          color = '232,169,59';
        } else {
          status = 'UNSAFE';
          color = '221,74,50';
        }

        ctx.fillStyle = `rgba(${color},0.16)`;
        ctx.fillRect(0, 0, boxCanvas.width, boxCanvas.height);
        ctx.strokeStyle = `rgb(${color})`;
        ctx.lineWidth = 3;
        ctx.strokeRect(1, 1, boxCanvas.width - 2, boxCanvas.height - 2);

        setZoneLabel('ZONE STATUS: ' + status);
        setZoneColor(`rgb(${color})`);

        ctx.strokeStyle = `rgb(${color})`;
        ctx.lineWidth = 2;
        detected.forEach((p) => {
          const [x, y, w, h] = p.bbox;
          ctx.strokeRect(x * scaleX, y * scaleY, w * scaleX, h * scaleY);
        });

        setHumanCount(detected.length);
        detectionsTotalRef.current += 1;
        if (detected.length > 0 && detectionsTotalRef.current % 20 === 1) {
          addLog(`${detected.length} human${detected.length > 1 ? 's' : ''} detected — zone ${status.toLowerCase()}.`);
        }
      } catch {
        /* skip frame on detector hiccup */
      }
    }
    detectRafRef.current = requestAnimationFrame(detectionLoop);
  }

  async function startDemo() {
    setStarting(true);
    setErrorBlock(null);

    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setErrorBlock('file');
      setStarting(false);
      return;
    }

    try {
      setStatusText('Requesting camera permission…');
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
      streamRef.current = stream;
      const video = videoRef.current!;
      video.srcObject = stream;
      await video.play();

      setStarted(true);
      setStatusColor('var(--caution)');
      setStatusText('Camera live — thermal view active. Loading detection model for RGB bounding boxes…');
      setModelStatus('Loading model…');

      runningRef.current = true;
      thermalRafRef.current = requestAnimationFrame(thermalLoop);

      const tf = await import('@tensorflow/tfjs');
      await tf.ready();
      const cocoSsd = await import('@tensorflow-models/coco-ssd');
      modelRef.current = await cocoSsd.load({ base: 'lite_mobilenet_v2' });
      setModelStatus('Model active');
      setStatusColor('var(--safe)');
      setStatusText('Camera and detection model both running. Bounding boxes below are real detections from your feed.');
      addLog('Camera stream started and detection model loaded.');
      detectRafRef.current = requestAnimationFrame(detectionLoop);
    } catch (err) {
      const error = err as Error & { name?: string };
      const isFileOrigin = location.protocol === 'file:';
      if (error.name === 'NotAllowedError' && isFileOrigin) {
        setErrorBlock('permission');
      } else if (runningRef.current) {
        setModelStatus('Model unavailable');
        setStatusColor('var(--caution)');
        setStatusText(
          `Thermal view is live. RGB bounding boxes are unavailable — the detection model failed to load (${error.message}). Check your internet connection or try a different browser.`,
        );
      } else {
        setStatusColor('var(--unsafe)');
        setStatusText(
          `Could not start camera: ${error.message}. If you denied the permission prompt, allow camera access for this site in your browser settings and try again.`,
        );
      }
    } finally {
      setStarting(false);
    }
  }

  return (
    <div>
      <div className="crumbs">Operations / Camera demo</div>
      <div className="page-title-row">
        <div>
          <h1>Live camera demo</h1>
          <p>Uses your device camera and a real object-detection model running locally in your browser — no video leaves your machine.</p>
        </div>
        <button className="btn primary" onClick={startDemo} disabled={starting || started}>
          {started ? 'Camera running' : starting ? 'Starting…' : 'Start camera'}
        </button>
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-body demo-status-body">
          {errorBlock === 'file' && (
            <div style={{ width: '100%' }}>
              <div className="demo-error-head">
                <span className="demo-error-dot" />
                <span className="demo-error-title">
                  Camera blocked — this page was opened as a local file, not served over a secure connection.
                </span>
              </div>
              <p className="demo-error-text">
                Browsers refuse camera access on <code>file://</code> pages for security — that is why no permission
                prompt appeared. This is not specific to Ignis Vision; it happens to every local HTML file. Fix it
                with a quick local server:
              </p>
              <p className="demo-code">
                cd path/to/downloaded/file
                <br />
                python3 -m http.server 8000
              </p>
              <p className="demo-error-text">
                Then open <code>http://localhost:8000/</code> in your browser — <code>localhost</code> counts as
                secure, so the camera prompt will appear normally. No Python? Any static server works (VS Code "Live
                Server" extension, <code>npx serve</code>, etc).
              </p>
            </div>
          )}
          {errorBlock === 'permission' && (
            <div style={{ width: '100%' }}>
              <div className="demo-error-head">
                <span className="demo-error-dot" />
                <span className="demo-error-title">
                  Camera blocked instantly, no prompt — this is the browser refusing camera on a local file, not a
                  real permission denial.
                </span>
              </div>
              <p className="demo-error-text">
                Opening this file directly (the address bar shows <code>file://...</code>) makes most browsers refuse
                camera access before a prompt even appears. Serve it locally instead:
              </p>
              <p className="demo-code-label">Option A — Python (usually already installed)</p>
              <p className="demo-code">
                cd path/to/downloaded/folder
                <br />
                python3 -m http.server 8000
              </p>
              <p className="demo-code-label">Option B — VS Code</p>
              <p className="demo-error-text">
                Install the "Live Server" extension, right-click the HTML file, choose "Open with Live Server."
              </p>
            </div>
          )}
          {!errorBlock && (
            <>
              <span className="demo-status-dot" style={{ background: statusColor }} />
              <span style={{ color: 'var(--text-mid)', fontSize: 12 }}>{statusText}</span>
            </>
          )}
        </div>
      </div>

      <div className="live-grid demo-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>Thermal (simulated)</h2>
            <span className="mono-dim">False-color overlay</span>
          </div>
          <div className="panel-body">
            <div className="cam-feed thermal demo-feed">
              <canvas ref={thermalCanvasRef} className="demo-canvas" />
              <div className="frame-label">LWIR SIMULATION</div>
              {started && (
                <div className="rec-badge">
                  <span className="rec-dot" />
                  LIVE
                </div>
              )}
            </div>
            <p className="demo-note">
              Real thermal sensors read heat, not visible light — this recolors your webcam feed to approximate that
              look and labels real detections as HUMAN. It is not a genuine temperature reading.
            </p>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>RGB camera — zone classification</h2>
            <span className="mono-dim">{modelStatus}</span>
          </div>
          <div className="panel-body">
            <div className="cam-feed rgb demo-feed">
              <video ref={videoRef} autoPlay muted playsInline className="demo-video" />
              <canvas ref={boxCanvasRef} className="demo-canvas demo-canvas-overlay" />
              <div className="frame-label" style={{ color: zoneColor }}>
                {zoneLabel}
              </div>
              {started && (
                <div className="rec-badge">
                  <span className="rec-dot" />
                  LIVE
                </div>
              )}
            </div>
            <p className="demo-note">
              Tint and zone status are derived from a real detection model (COCO-SSD via TensorFlow.js) counting
              people in your feed — more people in frame reads as higher caution, matching the OR-gate logic from the
              proposal.
            </p>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Fake structural map</h2>
            <span className="mono-dim">Click a zone to cycle status</span>
          </div>
          <div className="panel-body">
            <div className="zonemap-legend">
              <div className="legend-item">
                <span className="legend-swatch" style={{ background: 'var(--safe)' }} />
                Safe
              </div>
              <div className="legend-item">
                <span className="legend-swatch" style={{ background: 'var(--caution)' }} />
                Caution
              </div>
              <div className="legend-item">
                <span className="legend-swatch" style={{ background: 'var(--unsafe)' }} />
                Unsafe
              </div>
            </div>
            <div className="zone-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
              {demoZones.map((z, i) => (
                <div className={'zone-cell ' + z.status} style={{ cursor: 'pointer' }} key={z.id} onClick={() => cycleZone(i)}>
                  <span className="zid">{z.id}</span>
                </div>
              ))}
            </div>
            <div className="demo-map-actions">
              <button className="btn" onClick={addZone}>
                + Add zone
              </button>
              <button className="btn" onClick={resetMap}>
                Reset map
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="bottom-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <div className="panel">
          <div className="panel-head">
            <h2>Humans detected — this session</h2>
            <span className="mono-dim">{humanCount} in frame</span>
          </div>
          <div className="panel-body">
            {people.length === 0 ? (
              <div style={{ fontSize: 11.5, color: 'var(--text-low)' }}>No detections yet.</div>
            ) : (
              <div className="humans-list">
                {people.map((p, i) => (
                  <div className="human-card" key={i}>
                    <div className="badge">P{i + 1}</div>
                    <div className="d">
                      <div className="z">Person detected</div>
                      <div className="c">Live camera frame</div>
                    </div>
                    <div className="conf">{Math.round(p.score * 100)}%</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>Detection log</h2>
          </div>
          <div className="panel-body">
            <div className="alerts-col" style={{ maxHeight: 160, overflowY: 'auto' }}>
              {log.length === 0 ? (
                <div style={{ fontSize: 11, color: 'var(--text-low)' }}>Log will appear once the camera and model are running.</div>
              ) : (
                log.map((entry) => (
                  <div className="alert info" key={entry.id}>
                    <div className="txt">
                      <p>{entry.text}</p>
                      <span>{entry.time}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
