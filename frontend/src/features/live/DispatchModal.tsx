import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCreateIncident, useResponders } from '../../api/incidents';
import { ApiError } from '../../api/errors';
import type { IncidentCreate, IncidentDetail } from '../../api/types';
import { Modal } from '../../components/Modal';
import { errorMessage } from '../../i18n';

type Row = { key: number; user_id: string; zone_code: string; device_label: string };
const STRUCTURES = ['commercial', 'residential', 'industrial', 'other'] as const;
const TYPES = ['structural', 'chemical', 'electrical', 'other'] as const;

/** Prototype dispatch modal → POST /incidents (incident, floors, zones, team in one go). */
export function DispatchModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (inc: IncidentDetail) => void;
}) {
  const { t } = useTranslation();
  const responders = useResponders();
  const create = useCreateIncident();
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('Lahore');
  const [structure, setStructure] = useState<(typeof STRUCTURES)[number]>('commercial');
  const [type, setType] = useState<(typeof TYPES)[number]>('structural');
  const [reportedBy, setReportedBy] = useState('Rescue 1122');
  const [floors, setFloors] = useState(2);
  const [perFloor, setPerFloor] = useState(4);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [rows, setRows] = useState<Row[]>([
    { key: 1, user_id: '', zone_code: '', device_label: '' },
  ]);
  const [error, setError] = useState<string | null>(null);

  const codes = useMemo(() => {
    const out: string[] = [];
    for (let f = 1; f <= floors; f++) for (let z = 1; z <= perFloor; z++) out.push(`F${f}-Z${z}`);
    return out;
  }, [floors, perFloor]);

  const setRow = (key: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const chosen = new Set(rows.map((r) => r.user_id).filter(Boolean));
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v || lo));

  async function submit() {
    if (!address.trim()) return setError(t('dispatch.addressRequired'));
    setError(null);
    const body: IncidentCreate = {
      address: address.trim(),
      city: city.trim() || null,
      structure_type: structure,
      incident_type: type,
      reported_by: reportedBy.trim() || null,
      floors,
      zones_per_floor: perFloor,
      zone_labels: Object.fromEntries(
        Object.entries(labels).filter(([c, l]) => codes.includes(c) && l.trim()),
      ),
      assignments: rows
        .filter((r) => r.user_id)
        .map((r) => ({
          user_id: r.user_id,
          zone_code: codes.includes(r.zone_code) ? r.zone_code : null,
          device_label: r.device_label.trim() || null,
        })),
    };
    try {
      onCreated(await create.mutateAsync(body));
    } catch (e) {
      setError(errorMessage(e instanceof ApiError ? e.code : undefined));
    }
  }

  return (
    <Modal
      wide
      title={t('dispatch.title')}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            className="btn primary"
            onClick={() => void submit()}
            disabled={create.isPending}
            data-testid="dispatch-submit"
          >
            {create.isPending ? t('dispatch.submitting') : t('dispatch.submit')}
          </button>
        </>
      }
    >
      {error && (
        <p className="error-text" role="alert" style={{ marginBlockEnd: 12 }}>
          {error}
        </p>
      )}
      <div className="form-section">
        <div className="sec-title">
          <span className="n">1</span>
          {t('dispatch.s1')}
        </div>
        <div className="field-row">
          <div>
            <label className="field-label" htmlFor="f-address">
              {t('dispatch.address')}
            </label>
            <input id="f-address" value={address} onChange={(e) => setAddress(e.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="f-city">
              {t('dispatch.city')}
            </label>
            <input id="f-city" value={city} onChange={(e) => setCity(e.target.value)} />
          </div>
        </div>
        <div className="field-row three">
          <div>
            <label className="field-label" htmlFor="f-structure">
              {t('dispatch.structureType')}
            </label>
            <select
              id="f-structure"
              value={structure}
              onChange={(e) => setStructure(e.target.value as typeof structure)}
            >
              {STRUCTURES.map((s) => (
                <option key={s} value={s}>
                  {t(`structure.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field-label" htmlFor="f-type">
              {t('dispatch.incidentType')}
            </label>
            <select
              id="f-type"
              value={type}
              onChange={(e) => setType(e.target.value as typeof type)}
            >
              {TYPES.map((s) => (
                <option key={s} value={s}>
                  {t(`incidentType.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field-label" htmlFor="f-reported">
              {t('dispatch.reportedBy')}
            </label>
            <input
              id="f-reported"
              value={reportedBy}
              onChange={(e) => setReportedBy(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="form-section">
        <div className="sec-title">
          <span className="n">2</span>
          {t('dispatch.s2')}
        </div>
        <div className="field-row">
          <div>
            <label className="field-label" htmlFor="f-floors">
              {t('dispatch.floors')}
            </label>
            <input
              id="f-floors"
              type="number"
              min={1}
              max={50}
              value={floors}
              onChange={(e) => setFloors(clamp(+e.target.value, 1, 50))}
            />
          </div>
          <div>
            <label className="field-label" htmlFor="f-zpf">
              {t('dispatch.zonesPerFloor')}
            </label>
            <input
              id="f-zpf"
              type="number"
              min={1}
              max={20}
              value={perFloor}
              onChange={(e) => setPerFloor(clamp(+e.target.value, 1, 20))}
            />
          </div>
        </div>
        <div className="zone-chip-list">
          {codes.map((c) => (
            <label className="zone-chip" key={c}>
              {c}
              <input
                aria-label={`${c} label`}
                placeholder="…"
                value={labels[c] ?? ''}
                onChange={(e) => setLabels((l) => ({ ...l, [c]: e.target.value }))}
              />
            </label>
          ))}
        </div>
        <div className="hint">{t('dispatch.zoneHint')}</div>
      </div>

      <div className="form-section">
        <div className="sec-title">
          <span className="n">3</span>
          {t('dispatch.s3')}
        </div>
        {responders.data?.length === 0 && <p className="muted">{t('dispatch.noResponders')}</p>}
        {rows.map((r, i) => (
          <div className="team-row-form" key={r.key} data-testid={`team-row-${i}`}>
            <select
              aria-label={t('dispatch.responder')}
              value={r.user_id}
              onChange={(e) => setRow(r.key, { user_id: e.target.value })}
            >
              <option value="">{t('dispatch.responder')}</option>
              {responders.data?.map((u) => (
                <option key={u.id} value={u.id} disabled={chosen.has(u.id) && u.id !== r.user_id}>
                  {u.full_name}
                  {u.active_incident_code
                    ? ` (${t('dispatch.busy', { code: u.active_incident_code })})`
                    : ''}
                </option>
              ))}
            </select>
            <select
              aria-label={t('dispatch.zone')}
              value={r.zone_code}
              onChange={(e) => setRow(r.key, { zone_code: e.target.value })}
            >
              <option value="">{t('dispatch.noZone')}</option>
              {codes.map((c) => (
                <option key={c} value={c}>
                  {c}
                  {labels[c] ? ` · ${labels[c]}` : ''}
                </option>
              ))}
            </select>
            <input
              aria-label={t('dispatch.device')}
              placeholder={t('dispatch.device')}
              value={r.device_label}
              onChange={(e) => setRow(r.key, { device_label: e.target.value })}
            />
            <button
              type="button"
              className="rm-btn"
              aria-label={t('dispatch.remove')}
              onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}
            >
              ✕
            </button>
          </div>
        ))}
        <button
          type="button"
          className="add-row-btn"
          onClick={() =>
            setRows((rs) => [
              ...rs,
              { key: Date.now(), user_id: '', zone_code: '', device_label: '' },
            ])
          }
        >
          {t('dispatch.addResponder')}
        </button>
      </div>
    </Modal>
  );
}
