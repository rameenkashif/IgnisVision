import { useTranslation } from 'react-i18next';
import type { ScenarioIn } from '../../api/training';

/** Bilingual scenario fields (create + edit). */
export function ScenarioFields({
  value,
  onChange,
}: {
  value: ScenarioIn;
  onChange: (v: ScenarioIn) => void;
}) {
  const { t } = useTranslation();
  const set = <K extends keyof ScenarioIn>(k: K, v: ScenarioIn[K]) =>
    onChange({ ...value, [k]: v });
  return (
    <div className="form-grid">
      <label>
        <span className="field-label">{t('admin.sc.titleEn')}</span>
        <input
          id="sc-title-en"
          value={value.title_en}
          onChange={(e) => set('title_en', e.target.value)}
          dir="ltr"
          required
        />
      </label>
      <label>
        <span className="field-label">{t('admin.sc.titleUr')}</span>
        <input
          id="sc-title-ur"
          value={value.title_ur}
          onChange={(e) => set('title_ur', e.target.value)}
          dir="rtl"
          lang="ur"
          required
        />
      </label>
      <label>
        <span className="field-label">{t('admin.sc.descEn')}</span>
        <textarea
          value={value.description_en ?? ''}
          onChange={(e) => set('description_en', e.target.value)}
          dir="ltr"
          rows={2}
        />
      </label>
      <label>
        <span className="field-label">{t('admin.sc.descUr')}</span>
        <textarea
          value={value.description_ur ?? ''}
          onChange={(e) => set('description_ur', e.target.value)}
          dir="rtl"
          lang="ur"
          rows={2}
        />
      </label>
      <label>
        <span className="field-label">{t('admin.sc.kind')}</span>
        <select
          id="sc-kind"
          value={value.kind}
          onChange={(e) => set('kind', e.target.value as ScenarioIn['kind'])}
        >
          {(['zone', 'posture', 'mixed'] as const).map((k) => (
            <option key={k} value={k}>
              {t(`trainer.kind.${k}`)}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="field-label">{t('admin.sc.difficulty')}</span>
        <input
          type="number"
          min={1}
          max={5}
          value={value.difficulty ?? 1}
          onChange={(e) => set('difficulty', Number(e.target.value))}
        />
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={value.is_active ?? true}
          onChange={(e) => set('is_active', e.target.checked)}
        />
        {t('admin.sc.active')}
      </label>
    </div>
  );
}
