import { useTranslation } from 'react-i18next';
import { POSTURE_LABELS, ZONE_LABELS } from '../../api/training';

const ZONE_ICON = { safe: '✓', caution: '!', unsafe: '✕', blocked: '⛔' } as const;
const POSTURE_ICON = { standing: '🧍', sitting: '🪑', lying: '🛌', bending: '🙇' } as const;

/** Big bilingual tap targets for the label of the selected region/person. */
export function LabelPicker({
  type,
  value,
  disabled,
  onPick,
}: {
  type: 'zone' | 'posture';
  value?: string;
  disabled?: boolean;
  onPick: (label: string) => void;
}) {
  const { t } = useTranslation();
  const labels = type === 'zone' ? ZONE_LABELS : POSTURE_LABELS;
  return (
    <div className="label-picker" role="group" aria-label={t(`trainer.pick.${type}`)}>
      {labels.map((l) => (
        <button
          key={l}
          type="button"
          className={`pick-btn ${type === 'zone' ? `st-${l}` : 'posture'}`}
          aria-pressed={value === l}
          disabled={disabled}
          onClick={() => onPick(l)}
          data-label={l}
        >
          <span aria-hidden="true" className="pick-icon">
            {type === 'zone'
              ? ZONE_ICON[l as keyof typeof ZONE_ICON]
              : POSTURE_ICON[l as keyof typeof POSTURE_ICON]}
          </span>
          {t(type === 'zone' ? `status.${l}` : `posture.${l}`)}
        </button>
      ))}
    </div>
  );
}
