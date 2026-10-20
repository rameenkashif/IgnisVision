import { useTranslation } from 'react-i18next';
import type { ZoneOut } from '../api/types';

/** Floors × zones grid (prototype "structural map"), top floor first. Status is shown as
 * fill + text; victims as a separate circular badge so they never read as a zone colour. */
export function ZoneGrid({
  zones,
  mode = 'live',
  onSelect,
  selectedId,
}: {
  zones: ZoneOut[];
  mode?: 'live' | 'briefing';
  onSelect?: (z: ZoneOut) => void;
  selectedId?: string | null;
}) {
  const { t } = useTranslation();
  const floors = [...new Set(zones.map((z) => z.floor_number))].sort((a, b) => b - a);
  const cols = Math.max(1, ...zones.map((z) => z.grid_col + 1));

  return (
    <div className="zone-grid-wrap">
      {floors.map((f) => (
        <div className="zone-floor" key={f}>
          <div className="zone-floor-label">{t('live.floor', { n: f })}</div>
          <div
            className="zone-grid"
            style={{ gridTemplateColumns: `repeat(${cols}, minmax(54px, 1fr))` }}
          >
            {zones
              .filter((z) => z.floor_number === f)
              .map((z) => {
                const status = mode === 'briefing' ? 'neutral' : z.status;
                return (
                  <button
                    type="button"
                    key={z.id}
                    className={`zone-cell st-${status}${selectedId === z.id ? ' selected' : ''}`}
                    data-zone={z.code}
                    data-status={z.status}
                    onClick={() => onSelect?.(z)}
                    aria-label={`${z.code} ${z.label ?? ''} — ${t(`status.${z.status}`)}`}
                  >
                    <span className="zid">
                      {z.code}
                      {z.label ? ` · ${z.label}` : ''}
                    </span>
                    {mode === 'live' && (
                      <span className="zstatus">
                        {z.stale ? t('status.stale') : t(`status.${z.status}`)}
                      </span>
                    )}
                    <span className="assignee">
                      {z.assignees.map((a) => a.full_name).join(', ') || '—'}
                    </span>
                    {z.victim_count > 0 && (
                      <span
                        className="victim-badge"
                        title={t('live.victimsInZone', { count: z.victim_count })}
                      >
                        {z.victim_count}
                      </span>
                    )}
                  </button>
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ZoneLegend({ mode = 'live' }: { mode?: 'live' | 'briefing' }) {
  const { t } = useTranslation();
  if (mode === 'briefing') {
    return (
      <div className="zonemap-legend">
        <span className="legend-item">
          <span className="legend-swatch st-neutral" />
          {t('live.assignedNotLive')}
        </span>
      </div>
    );
  }
  return (
    <div className="zonemap-legend">
      {(['safe', 'caution', 'unsafe', 'blocked', 'unclassified'] as const).map((s) => (
        <span className="legend-item" key={s}>
          <span className={`legend-swatch st-${s}`} />
          {t(`status.${s}`)}
        </span>
      ))}
      <span className="legend-item">
        <span className="victim-badge static">1</span>
        {t('live.humans')}
      </span>
    </div>
  );
}
