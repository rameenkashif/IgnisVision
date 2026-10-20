import type { TFunction } from 'i18next';

/** Fusion reasons arrive as {key, params}; damage classes inside params are translated too. */
export function reasonText(
  t: TFunction,
  r: { key: string; params?: Record<string, unknown> },
): string {
  const params: Record<string, unknown> = { ...(r.params ?? {}) };
  if (typeof params.cls === 'string') params.cls = t(`damage.${params.cls}`);
  return t(r.key, { ...params, defaultValue: r.key });
}
