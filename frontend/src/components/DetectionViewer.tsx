import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useFrames, type DetectionOut } from '../api/thermal';

/** Thermal media with person boxes, posture and priority. Videos are shown as the 2 fps frames
 * the model analysed (always playable, boxes exactly aligned); the original stays a link. */
export function DetectionViewer({
  mediaId,
  url,
  kind,
  detections,
  compact = false,
  ready = true,
}: {
  mediaId: string;
  url: string;
  kind: 'thermal_image' | 'thermal_video';
  detections: DetectionOut[];
  compact?: boolean;
  ready?: boolean;
}) {
  const { t } = useTranslation();
  const isVideo = kind === 'thermal_video';
  const frames = useFrames(mediaId, isVideo && ready);
  const list = useMemo(() => frames.data ?? [], [frames.data]);
  const [pos, setPos] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);

  // Default frame: the one with the highest-priority person (compact) or the first.
  const bestIndex = useMemo(() => {
    if (!detections.length) return 0;
    const top = detections.reduce((a, b) => (b.rpi_score > a.rpi_score ? b : a));
    return Math.max(
      0,
      list.findIndex((f) => f.frame_index === top.frame_index),
    );
  }, [detections, list]);
  const at = pos ?? (compact ? bestIndex : 0);
  const frame = list[at];

  useEffect(() => {
    if (!playing || !list.length) return;
    const id = window.setInterval(() => setPos((p) => ((p ?? 0) + 1) % list.length), 500);
    return () => window.clearInterval(id);
  }, [playing, list.length]);

  const shown = isVideo
    ? detections.filter((d) => d.frame_index === frame?.frame_index)
    : detections;
  const src = isVideo ? frame?.url : url;

  return (
    <div className={`det-viewer${compact ? ' compact' : ''}`} data-testid="detection-viewer">
      <div className="det-stage">
        {src ? <img src={src} alt="" /> : <div className="feed-placeholder" />}
        <svg className="det-boxes" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
          {shown.map((d) => {
            const [x1, y1, x2, y2] = d.bbox as [number, number, number, number];
            return (
              <rect
                key={d.id}
                className={`prio-${d.rpi_band}`}
                x={x1}
                y={y1}
                width={x2 - x1}
                height={y2 - y1}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
        </svg>
        <div className="det-labels" dir="ltr">
          {shown.map((d) => {
            const [x1, , , y2] = d.bbox as [number, number, number, number];
            return (
              <span
                key={d.id}
                className={`det-label prio-${d.rpi_band}`}
                style={{ left: `${x1 * 100}%`, top: `${Math.min(y2, 0.92) * 100}%` }}
              >
                {t(`posture.${d.posture}`)}
                {d.low_confidence ? ' ⚠' : ''} · {t(`band.${d.rpi_band}`)}
              </span>
            );
          })}
        </div>
        {isVideo && frame && (
          <span className="det-time">
            {t('analysis.frame', { t: (frame.timestamp_ms / 1000).toFixed(1) })}
          </span>
        )}
      </div>
      {isVideo && !compact && list.length > 1 && (
        <div className="det-controls">
          <button
            type="button"
            className="btn"
            onClick={() => setPlaying((p) => !p)}
            aria-label={playing ? 'Pause' : 'Play'}
          >
            {playing ? '❚❚' : '▶'}
          </button>
          <input
            type="range"
            min={0}
            max={list.length - 1}
            value={at}
            aria-label={t('analysis.viewer')}
            onChange={(e) => {
              setPlaying(false);
              setPos(Number(e.target.value));
            }}
          />
          <a className="btn" href={url} target="_blank" rel="noreferrer">
            {t('analysis.original')}
          </a>
        </div>
      )}
      {ready && !detections.length && <p className="hint">{t('analysis.noPeople')}</p>}
    </div>
  );
}
