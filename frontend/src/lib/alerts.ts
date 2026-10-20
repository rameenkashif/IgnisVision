import type { TFunction } from 'i18next';
import type { AlertOut } from '../api/types';

/** Render an alert in the viewer's language from its key + params (HANDOFF §5). */
export function alertText(t: TFunction, a: AlertOut): string {
  const params: Record<string, unknown> = { ...a.message_params };
  for (const k of ['from', 'to', 'status']) {
    if (typeof params[k] === 'string') params[k] = t(`status.${params[k]}`);
  }
  return t(a.message_key, { ...params, defaultValue: a.message_key });
}
