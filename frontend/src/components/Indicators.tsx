import { useTranslation } from 'react-i18next';
import { useOnline } from '../lib/online';
import { useUi } from '../stores/ui';

/** Internet + realtime-link state. Colour always paired with a text label. */
export function ConnIndicator() {
  const { t } = useTranslation();
  const online = useOnline();
  const link = useUi((s) => s.link);
  const [cls, label] = !online
    ? ['bad', t('shell.offline')]
    : link === 'lost' || link === 'connecting'
      ? ['warn', t('shell.liveLost')]
      : link === 'open'
        ? ['ok', t('shell.liveOk')]
        : ['ok', t('shell.online')];
  return (
    <span className={`chip ${cls}`} role="status" aria-live="polite" data-testid="conn-indicator">
      <span className="dot" aria-hidden="true" />
      <span className="chip-label">{label}</span>
      <span className="sr-only">{label}</span>
    </span>
  );
}

/** Shown only on screens that use the camera. */
export function CamIndicator() {
  const { t } = useTranslation();
  const camera = useUi((s) => s.camera);
  const [cls, label] =
    camera === 'on'
      ? ['ok', t('shell.cameraOn')]
      : camera === 'blocked'
        ? ['bad', t('shell.cameraBlocked')]
        : ['', t('shell.cameraOff')];
  return (
    <span className={`chip ${cls}`} role="status" data-testid="cam-indicator">
      <span aria-hidden="true">◎</span>
      <span className="chip-label">{label}</span>
      <span className="sr-only">{label}</span>
    </span>
  );
}
