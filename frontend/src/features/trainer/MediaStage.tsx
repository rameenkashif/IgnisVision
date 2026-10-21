import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { StageItem } from '../../api/training';

export type StageLabel = { text: string; tone?: string };

function centroid(poly: [number, number][]): [number, number] {
  const n = poly.length || 1;
  return [poly.reduce((s, p) => s + p[0], 0) / n, poly.reduce((s, p) => s + p[1], 0) / n];
}

/** Training media (image, or video with play/pause) with the regions and people to label drawn
 * on top in normalised coordinates. Shapes are keyboard-focusable; labels sit on each target. */
export function MediaStage({
  item,
  labels = {},
  shapeClass,
  selectedId,
  onSelect,
  overlay,
  onStagePointer,
  videoRef,
  testId = 'media-stage',
}: {
  item: StageItem;
  labels?: Record<string, StageLabel>;
  shapeClass?: (id: string) => string;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  overlay?: ReactNode;
  onStagePointer?: (kind: 'down' | 'move' | 'up', p: [number, number], e: PointerEvent) => void;
  videoRef?: (el: HTMLVideoElement | null) => void;
  testId?: string;
}) {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement | null>(null);
  const svg = useRef<SVGSVGElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const frameS = item.frame_s ?? 0;

  useEffect(() => {
    const v = video.current;
    if (v && v.readyState >= 1) v.currentTime = frameS;
  }, [frameS, item.media_url]);

  const toUnit = (e: PointerEvent): [number, number] => {
    const r = svg.current!.getBoundingClientRect();
    const clamp = (v: number) => Math.min(1, Math.max(0, v));
    return [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)];
  };
  const pointer = (kind: 'down' | 'move' | 'up') =>
    onStagePointer ? (e: PointerEvent) => onStagePointer(kind, toUnit(e), e) : undefined;

  const shape = (id: string, label: string) => ({
    className: `target ${shapeClass?.(id) ?? ''}${selectedId === id ? ' selected' : ''}`,
    'data-target': id,
    role: onSelect ? 'button' : undefined,
    tabIndex: onSelect ? 0 : undefined,
    'aria-label': label,
    'aria-pressed': onSelect ? selectedId === id : undefined,
    onClick: onSelect ? () => onSelect(id) : undefined,
    onKeyDown: onSelect
      ? (e: React.KeyboardEvent) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect(id);
          }
        }
      : undefined,
  });

  return (
    <div className="stage-wrap" data-testid={testId}>
      <div className="stage">
        {item.media_kind === 'video' ? (
          <video
            ref={(el) => {
              video.current = el;
              videoRef?.(el);
            }}
            src={item.media_url ?? undefined}
            playsInline
            muted
            preload="auto"
            onLoadedMetadata={(e) => (e.currentTarget.currentTime = frameS)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
        ) : (
          <img src={item.media_url ?? undefined} alt="" draggable={false} />
        )}
        <svg
          ref={svg}
          className={`stage-svg${onStagePointer ? ' drawing' : ''}`}
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          onPointerDown={pointer('down')}
          onPointerMove={pointer('move')}
          onPointerUp={pointer('up')}
        >
          {item.regions.map((r, i) => (
            <polygon
              key={r.id}
              points={r.polygon.map((p) => p.join(',')).join(' ')}
              vectorEffect="non-scaling-stroke"
              {...shape(
                r.id,
                `${t('trainer.region', { n: i + 1 })}${labels[r.id] ? `: ${labels[r.id].text}` : ''}`,
              )}
            />
          ))}
          {item.people.map((p, i) => (
            <rect
              key={p.id}
              x={p.bbox[0]}
              y={p.bbox[1]}
              width={p.bbox[2] - p.bbox[0]}
              height={p.bbox[3] - p.bbox[1]}
              vectorEffect="non-scaling-stroke"
              {...shape(
                p.id,
                `${t('trainer.person', { n: i + 1 })}${labels[p.id] ? `: ${labels[p.id].text}` : ''}`,
              )}
            />
          ))}
          {overlay}
        </svg>
        <div className="stage-labels" dir="ltr" aria-hidden="true">
          {item.regions.map((r, i) => {
            const [x, y] = centroid(r.polygon);
            return (
              <span
                key={r.id}
                className={`stage-label ${labels[r.id]?.tone ?? ''}`}
                style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
              >
                <b>{i + 1}</b>
                {labels[r.id] && <span>{labels[r.id].text}</span>}
              </span>
            );
          })}
          {item.people.map((p, i) => (
            <span
              key={p.id}
              className={`stage-label person ${labels[p.id]?.tone ?? ''}`}
              style={{ left: `${p.bbox[0] * 100}%`, top: `${p.bbox[1] * 100}%` }}
            >
              <b>{i + 1}</b>
              {labels[p.id] && <span>{labels[p.id].text}</span>}
            </span>
          ))}
        </div>
      </div>
      {item.media_kind === 'video' && (
        <div className="stage-controls">
          <button
            type="button"
            className="btn"
            onClick={() => (playing ? video.current?.pause() : void video.current?.play())}
            data-testid="stage-play"
          >
            {playing ? `❚❚ ${t('trainer.pause')}` : `▶ ${t('trainer.play')}`}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              video.current?.pause();
              if (video.current) video.current.currentTime = frameS;
            }}
          >
            {t('trainer.labelledFrame', { t: frameS.toFixed(1) })}
          </button>
        </div>
      )}
    </div>
  );
}
