import i18n from '../i18n';

function locale(): string {
  return i18n.language === 'ur' ? 'ur-PK' : 'en-GB';
}

export function formatTime(iso: string | Date | null | undefined, seconds = false): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString(locale(), {
    hour: '2-digit',
    minute: '2-digit',
    ...(seconds ? { second: '2-digit' } : {}),
  });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(locale(), {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`;
}
