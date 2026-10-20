import { useTranslation } from 'react-i18next';
import type { Kpis } from '../api/types';

const ORDER = ['safe', 'caution', 'unsafe', 'blocked', 'unclassified'] as const;
const COLOR: Record<(typeof ORDER)[number], string> = {
  safe: 'var(--safe)',
  caution: 'var(--caution)',
  unsafe: 'var(--unsafe)',
  blocked: 'var(--blocked)',
  unclassified: 'var(--unclassified)',
};

/** Zone classification donut incl. blocked and unclassified (HANDOFF §4.2). */
export function Donut({ kpis }: { kpis: Kpis }) {
  const { t } = useTranslation();
  const total = kpis.zones_total || 1;
  let offset = 25;
  return (
    <div className="donut-wrap">
      <svg
        width="100"
        height="100"
        viewBox="0 0 42 42"
        role="img"
        aria-label={t('live.zoneClassification')}
      >
        <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="var(--bg-3)" strokeWidth="6" />
        {ORDER.map((s) => {
          const pct = (100 * (kpis.zones_by_status[s] ?? 0)) / total;
          const el = (
            <circle
              key={s}
              cx="21"
              cy="21"
              r="15.9"
              fill="transparent"
              stroke={COLOR[s]}
              strokeWidth="6"
              strokeDasharray={`${pct} ${100 - pct}`}
              strokeDashoffset={offset}
            />
          );
          offset -= pct;
          return el;
        })}
      </svg>
      <div className="donut-legend">
        {ORDER.map((s) => (
          <div className="row" key={s}>
            <span className={`sw st-${s}`} />
            {t(`status.${s}`)}
            <span className="pct">
              {Math.round((100 * (kpis.zones_by_status[s] ?? 0)) / total)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Evacuation threshold: counts only currently classified zones; unclassified shown apart. */
export function EvacBar({ kpis }: { kpis: Kpis }) {
  const { t } = useTranslation();
  const params = { pct: kpis.evac_ok_pct, threshold: kpis.evacuation_threshold_pct };
  const [cls, icon, title, sub] =
    kpis.evac_ok_pct === null
      ? ['unknown', '?', t('live.evacUnknownTitle'), t('live.evacUnknownSub')]
      : kpis.below_threshold
        ? ['warn', '!', t('live.evacWarnTitle'), t('live.evacWarnSub', params)]
        : ['ok', '✓', t('live.evacOkTitle'), t('live.evacOkSub', params)];
  return (
    <div className={`evac-bar ${cls}`} data-testid="evac-bar">
      <div className="ic" aria-hidden="true">
        {icon}
      </div>
      <div>
        <div className="t">{title}</div>
        <div className="s">{sub}</div>
        {kpis.unclassified_pct > 0 && (
          <div className="s">{t('live.unclassifiedShare', { pct: kpis.unclassified_pct })}</div>
        )}
      </div>
    </div>
  );
}
