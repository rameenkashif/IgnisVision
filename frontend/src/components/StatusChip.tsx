import { useTranslation } from 'react-i18next';
import type { ZoneStatus } from '../api/types';

const ICON: Record<ZoneStatus, string> = {
  safe: '✓',
  caution: '!',
  unsafe: '✕',
  blocked: '⛔',
  unclassified: '?',
};

/** Colour + icon + text label, always (colour-blind safe, SRS §3.1.2). */
export function StatusChip({ status, large = false }: { status: ZoneStatus; large?: boolean }) {
  const { t } = useTranslation();
  return (
    <span className={`status-chip st-${status}${large ? ' large' : ''}`} data-status={status}>
      <span aria-hidden="true">{ICON[status]}</span>
      {t(`status.${status}`)}
    </span>
  );
}
