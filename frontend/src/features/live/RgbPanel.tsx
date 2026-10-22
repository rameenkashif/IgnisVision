import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ZoneOut } from '../../api/types';
import { StatusChip } from '../../components/StatusChip';
import { formatTime } from '../../lib/format';

/** Latest analysed frame per zone, with the segmentation/damage overlay (Q11 default). */
export function RgbPanel({ zones }: { zones: ZoneOut[] }) {
  const { t } = useTranslation();
  const withFrames = zones.filter((z) => z.frame_url);
  const [selected, setSelected] = useState<string | null>(null);
  const [overlay, setOverlay] = useState(true);
  const zone = withFrames.find((z) => z.id === selected) ?? withFrames[0];

  return (
    <div className="panel" data-testid="rgb-panel">
      <div className="panel-head">
        <h2>{t('live.rgb')}</h2>
        {zone && (
          <label className="meta" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
            <input
              type="checkbox"
              style={{ width: 'auto', minHeight: 0 }}
              checked={overlay}
              onChange={(e) => setOverlay(e.target.checked)}
            />
            {t('live.overlayToggle')}
          </label>
        )}
      </div>
      <div className="panel-body">
        {!zone ? (
          <div className="feed-placeholder">{t('live.noRgb')}</div>
        ) : (
          <>
            {withFrames.length > 1 && (
              <div className="frame-tabs" role="group">
                {withFrames.map((z) => (
                  <button
                    key={z.id}
                    type="button"
                    aria-pressed={z.id === zone.id}
                    onClick={() => setSelected(z.id)}
                  >
                    {z.code}
                  </button>
                ))}
              </div>
            )}
            <div className="frame-view">
              <img src={zone.frame_url!} alt={`${zone.code}`} />
              {overlay && zone.overlay_url && (
                <img className="overlay" src={zone.overlay_url} alt="" />
              )}
              <span className="frame-label">
                {zone.code} · {formatTime(zone.status_updated_at, true)}
              </span>
              <span className="frame-chip">
                <StatusChip status={zone.status} />
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
