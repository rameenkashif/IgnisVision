import { useTranslation } from 'react-i18next';
import type { VictimOut } from '../api/thermal';
import { pct } from '../lib/format';
import { RpiChip } from './RpiChip';

/** People ranked by Rescue Priority Index (HANDOFF §4.2). */
export function VictimList({
  victims,
  onStatus,
  onSelect,
}: {
  victims: VictimOut[];
  onStatus?: (v: VictimOut, status: VictimOut['status']) => void;
  onSelect?: (v: VictimOut) => void;
}) {
  const { t } = useTranslation();
  if (!victims.length) return <p className="muted">{t('victims.none')}</p>;
  let rank = 0;
  return (
    <>
      <ol className="humans-list" data-testid="victim-list">
        {victims.map((v) => {
          const active = v.status === 'detected';
          if (active) rank++;
          return (
            <li
              key={v.id}
              className={`human-card${active ? '' : ' done'}`}
              data-band={v.rpi_band}
              data-status={v.status}
            >
              <button type="button" className="human-main" onClick={() => onSelect?.(v)}>
                <span className="badge">{active ? rank : '–'}</span>
                <span className="d">
                  <span className="z">
                    {t(`posture.${v.posture}`)}
                    {v.low_confidence && (
                      <span className="lowconf"> · ⚠ {t('victims.lowConfidence')}</span>
                    )}
                  </span>
                  <span className="c">
                    {v.zone_code ?? '—'} · {t(`analysis.source.${v.source}`)} ·{' '}
                    {pct(v.detection_confidence)}
                    {!active && ` · ${t(`victims.status.${v.status}`)}`}
                  </span>
                </span>
                <RpiChip band={v.rpi_band} score={v.rpi_score} />
              </button>
              {onStatus && (
                <span className="human-actions">
                  {active ? (
                    <>
                      <button type="button" className="btn" onClick={() => onStatus(v, 'rescued')}>
                        {t('victims.rescued')}
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => onStatus(v, 'false_positive')}
                      >
                        {t('victims.falsePositive')}
                      </button>
                    </>
                  ) : (
                    <button type="button" className="btn" onClick={() => onStatus(v, 'detected')}>
                      {t('victims.restore')}
                    </button>
                  )}
                </span>
              )}
            </li>
          );
        })}
      </ol>
      <p className="hint">{t('victims.disclaimer')}</p>
    </>
  );
}
