import { useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCaptureTargets } from '../../api/capture';
import { keys } from '../../api/incidents';
import type { IncidentDetail } from '../../api/types';
import { PageHeader } from '../../components/PageHeader';
import { StatusChip } from '../../components/StatusChip';
import { ZoneGrid } from '../../components/ZoneGrid';
import { currentLang } from '../../i18n';
import {
  cameraErrorCode,
  grabJpeg,
  openRearCamera,
  ScreenWakeLock,
  type CameraError,
} from '../../lib/camera';
import { formatTime } from '../../lib/format';
import { reasonText } from '../../lib/reasons';
import { canSpeak, onVoicesChanged, speak } from '../../lib/tts';
import { usePrefs } from '../../stores/prefs';
import { useUi } from '../../stores/ui';
import {
  CaptureClient,
  type CaptureAlert,
  type CaptureState,
  type ZoneResult,
} from '../../ws/capture';
import { useIncidentStream } from '../../ws/hooks';

/** Zone capture (HANDOFF §11): mobile-first, big controls, spoken alerts, compact zone map. */
export function CapturePage() {
  const { t } = useTranslation();
  const targets = useCaptureTargets();
  const setCamera = useUi((s) => s.setCamera);
  const setKeepAlive = useUi((s) => s.setKeepAlive);
  const voiceOn = usePrefs((s) => s.voiceAlerts);

  const [incidentId, setIncidentId] = useState<string>('');
  const [zoneId, setZoneId] = useState<string>('');
  const [state, setState] = useState<CaptureState>('idle');
  const [fps, setFps] = useState('1');
  const [result, setResult] = useState<ZoneResult | null>(null);
  const [lastAt, setLastAt] = useState<Date | null>(null);
  const [spokenText, setSpokenText] = useState<string | null>(null);
  const [voiceMissing, setVoiceMissing] = useState(false);
  const [camError, setCamError] = useState<CameraError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [overlay, setOverlay] = useState(true);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const clientRef = useRef<CaptureClient | null>(null);
  const wakeRef = useRef(new ScreenWakeLock());

  const list = useMemo(() => targets.data ?? [], [targets.data]);
  const target = list.find((x) => x.incident.id === incidentId) ?? list[0];
  const zones = target?.zones ?? [];
  const zone = zones.find((z) => z.id === zoneId) ?? zones[0];

  // Live zone map: the incident channel pushes full aggregates into the query cache.
  useIncidentStream(target?.incident.id);
  const live = useQuery<IncidentDetail>({
    queryKey: keys.incident(target?.incident.id ?? ''),
    queryFn: () => Promise.reject(new Error('push-only')),
    enabled: false,
  });
  const mapZones = live.data?.zones ?? zones;

  const say = useCallback(
    (text: string) => {
      setSpokenText(text);
      if (!voiceOn) return;
      if (speak(text, currentLang()) === 'unavailable') setVoiceMissing(true);
    },
    [voiceOn],
  );

  useEffect(() => {
    const check = () => setVoiceMissing(voiceOn && !canSpeak(currentLang()));
    check();
    return onVoicesChanged(check);
  }, [voiceOn]);

  const stop = useCallback(() => {
    clientRef.current?.stop();
    clientRef.current = null;
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    wakeRef.current.release();
    setCamera('off');
    setKeepAlive(false);
  }, [setCamera, setKeepAlive]);

  useEffect(() => stop, [stop]); // leaving the page ends capture

  async function start() {
    if (!zone) return;
    setCamError(null);
    setNotice(null);
    try {
      streamRef.current = await openRearCamera();
    } catch (e) {
      const code = cameraErrorCode(e);
      setCamError(code);
      setCamera('blocked');
      say(t('voice.camera_error'));
      return;
    }
    const video = videoRef.current!;
    video.srcObject = streamRef.current;
    await video.play().catch(() => undefined);
    setCamera('on');
    setKeepAlive(true);
    void wakeRef.current.acquire();
    const client = new CaptureClient(zone.id, {
      grab: () => grabJpeg(video, canvasRef.current!),
      onState: (s, detail) => {
        setState(s);
        if (s === 'streaming') {
          setFps(detail ?? '1');
          say(t('voice.capture_started', { zone: zone.code }));
        }
        if (s === 'error') {
          setNotice(t(`errors.${detail}`, { defaultValue: t('errors.unknown') }));
          stop();
        }
      },
      onResult: (r) => {
        setResult(r);
        setLastAt(new Date());
      },
      onAlert: (a: CaptureAlert) => {
        const params = { ...a.params, to: a.params.to ? t(`status.${a.params.to}`) : undefined };
        const key = `voice.${a.alert_type}`;
        say(t(key, { ...params, defaultValue: t(a.message_key, params) }));
      },
      onFrameError: (code) => setNotice(t('capture.frameError', { code })),
    });
    clientRef.current = client;
    client.start();
  }

  const capturing = state === 'connecting' || state === 'streaming' || state === 'reconnecting';
  const status = result?.status ?? 'unclassified';

  if (!targets.isLoading && !list.length) {
    return (
      <>
        <PageHeader page="capture" />
        <div className="empty-state" data-testid="capture-empty">
          <p>{t('capture.noTargets')}</p>
        </div>
      </>
    );
  }

  return (
    <div className="capture" data-testid="capture-page">
      <PageHeader page="capture" />
      <div className="capture-pickers">
        {list.length > 1 && (
          <label>
            <span className="field-label">{t('capture.incident')}</span>
            <select
              value={target?.incident.id ?? ''}
              disabled={capturing}
              onChange={(e) => {
                setIncidentId(e.target.value);
                setZoneId('');
              }}
            >
              {list.map((x) => (
                <option key={x.incident.id} value={x.incident.id}>
                  {x.incident.code} · {x.incident.address}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          <span className="field-label">{t('capture.zone')}</span>
          <select
            value={zone?.id ?? ''}
            disabled={capturing}
            onChange={(e) => setZoneId(e.target.value)}
            data-testid="capture-zone"
          >
            {zones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.assigned_to_me ? '★ ' : ''}
                {z.code}
                {z.label ? ` · ${z.label}` : ''}
                {z.assigned_to_me ? ` (${t('capture.assignedToYou')})` : ''}
              </option>
            ))}
          </select>
        </label>
      </div>

      {camError && (
        <div className="banner bad" role="alert" data-testid="camera-error">
          {t(`camera.${camError}`)}
        </div>
      )}
      {notice && (
        <div className="banner warn" role="alert">
          {notice}
        </div>
      )}
      {voiceMissing && spokenText && (
        <div className="banner warn" role="status">
          {t('capture.voiceUnavailable')}
        </div>
      )}

      <div className="capture-stage">
        <div className="capture-video">
          <video ref={videoRef} muted playsInline aria-hidden="true" />
          {overlay && result?.overlay_url && (
            <img className="capture-overlay" src={result.overlay_url} alt="" />
          )}
          {!capturing && <div className="capture-hint">{t('capture.waiting')}</div>}
          <div className="capture-status" aria-live="assertive" data-testid="capture-status">
            <StatusChip status={status} large />
          </div>
          <canvas ref={canvasRef} hidden />
        </div>

        <button
          type="button"
          className={`capture-btn ${capturing ? 'stop' : 'start'}`}
          onClick={() => (capturing ? stop() : void start())}
          disabled={!zone}
          data-testid="capture-toggle"
        >
          {capturing ? t('capture.stop') : t('capture.start')}
        </button>
        <div className="capture-meta" data-testid="capture-meta" data-state={state}>
          {state === 'connecting' && t('capture.connecting')}
          {state === 'reconnecting' && t('capture.reconnecting')}
          {state === 'streaming' && t('capture.streaming', { fps })}
          {lastAt && result && (
            <>
              {' '}
              · {t('capture.lastUpdate', { time: formatTime(lastAt, true), ms: result.latency_ms })}
            </>
          )}
          <label className="capture-overlay-toggle">
            <input
              type="checkbox"
              checked={overlay}
              onChange={(e) => setOverlay(e.target.checked)}
            />{' '}
            {t('capture.overlay')}
          </label>
        </div>
      </div>

      {spokenText && (
        <div className="capture-spoken" role="status" data-testid="capture-spoken">
          🔊 {spokenText}
        </div>
      )}

      <div className="capture-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>{t('capture.reasonsTitle')}</h2>
          </div>
          <div className="panel-body">
            {result && !result.analysable && <p className="muted">{t('capture.notAnalysable')}</p>}
            <ul className="reasons" data-testid="capture-reasons">
              {result?.reasons.map((r, i) => <li key={i}>{reasonText(t, r)}</li>)}
            </ul>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>{t('capture.zoneMap')}</h2>
          </div>
          <div className="panel-body">
            <ZoneGrid
              zones={mapZones}
              selectedId={zone?.id}
              onSelect={(z) => !capturing && setZoneId(z.id)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
