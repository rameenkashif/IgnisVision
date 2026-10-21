import { useTranslation } from 'react-i18next';

type Band = 'critical' | 'high' | 'medium' | 'low';

/** Victim priority: round badge + label in the separate --prio-* palette, so it never reads
 * as a zone colour (SRS §3.1.2). */
export function RpiChip({ band, score }: { band: Band; score?: number }) {
  const { t } = useTranslation();
  return (
    <span className={`rpi-chip prio-${band}`} data-band={band}>
      <span className="rpi-dot" aria-hidden="true" />
      {t(`band.${band}`)}
      {score !== undefined && <span className="rpi-score">{score.toFixed(2)}</span>}
    </span>
  );
}
