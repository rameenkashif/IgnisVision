import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import type { DispatchTeamDraft, DispatchZoneDraft } from '../../state/IncidentContext';
import { useIncident } from '../../state/IncidentContext';

interface DispatchModalProps {
  open: boolean;
  onClose: () => void;
}

function genZones(floors: number, perFloor: number): DispatchZoneDraft[] {
  const zones: DispatchZoneDraft[] = [];
  for (let f = 1; f <= floors; f++) {
    for (let z = 1; z <= perFloor; z++) {
      zones.push({ id: `F${f}-${String(z).padStart(2, '0')}`, label: `Floor ${f} — Zone ${z}`, floor: f });
    }
  }
  return zones;
}

export function DispatchModal({ open, onClose }: DispatchModalProps) {
  const { createIncident } = useIncident();

  const [location, setLocation] = useState('Gul Plaza, M.A Jinnah Road');
  const [city, setCity] = useState('Karachi');
  const [structType, setStructType] = useState('Commercial');
  const [incidentType, setIncidentType] = useState('Structural fire');
  const [reportedBy, setReportedBy] = useState('Rescue 1122');

  const [floors, setFloors] = useState(2);
  const [zonesPerFloor, setZonesPerFloor] = useState(4);
  const [zoneDraft, setZoneDraft] = useState<DispatchZoneDraft[]>([]);

  const [teamRows, setTeamRows] = useState<DispatchTeamDraft[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setZoneDraft((current) => (current.length ? current : genZones(floors, zonesPerFloor)));
    setTeamRows((current) => (current.length ? current : [{ name: 'Team member 1', zone: '', cam: 1 }]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (zoneDraft.length === 0) return;
    setTeamRows((rows) => rows.map((r) => (r.zone ? r : { ...r, zone: zoneDraft[0].id })));
  }, [zoneDraft]);

  function handleGenZones() {
    setZoneDraft(genZones(floors, zonesPerFloor));
  }

  function updateZoneLabel(idx: number, label: string) {
    setZoneDraft((zones) => zones.map((z, i) => (i === idx ? { ...z, label } : z)));
  }

  function addTeamRow() {
    setTeamRows((rows) => [
      ...rows,
      { name: `Team member ${rows.length + 1}`, zone: zoneDraft[0]?.id ?? '', cam: (rows.length % 3) + 1 },
    ]);
  }

  function removeTeamRow(idx: number) {
    setTeamRows((rows) => rows.filter((_, i) => i !== idx));
  }

  function updateTeamRow(idx: number, patch: Partial<DispatchTeamDraft>) {
    setTeamRows((rows) => rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (teamRows.length === 0 || zoneDraft.length === 0) {
      setError('Add at least one zone and one dispatched firefighter.');
      return;
    }
    setError('');
    createIncident({ location, city, structType, incidentType, reportedBy, zones: zoneDraft, teams: teamRows });
    onClose();
  }

  return (
    <div className={'modal-overlay' + (open ? ' open' : '')}>
      <form className="modal" onSubmit={handleSubmit}>
        <div className="modal-head">
          <h2>Log new emergency</h2>
          <button type="button" className="modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="form-section">
            <div className="sec-title">
              <span className="n">1</span>Incident location
            </div>
            <div className="field-row">
              <div className="fg">
                <label className="field-label">Address</label>
                <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Gul Plaza, M.A Jinnah Road" />
              </div>
              <div className="fg">
                <label className="field-label">City</label>
                <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Karachi" />
              </div>
            </div>
            <div className="field-row three">
              <div className="fg">
                <label className="field-label">Structure type</label>
                <select value={structType} onChange={(e) => setStructType(e.target.value)}>
                  <option>Commercial</option>
                  <option>Residential</option>
                  <option>Industrial</option>
                </select>
              </div>
              <div className="fg">
                <label className="field-label">Incident type</label>
                <select value={incidentType} onChange={(e) => setIncidentType(e.target.value)}>
                  <option>Structural fire</option>
                  <option>Chemical fire</option>
                  <option>Electrical fire</option>
                </select>
              </div>
              <div className="fg">
                <label className="field-label">Reported by</label>
                <input value={reportedBy} onChange={(e) => setReportedBy(e.target.value)} />
              </div>
            </div>
          </div>

          <div className="form-section">
            <div className="sec-title">
              <span className="n">2</span>Structural map — zones
            </div>
            <div className="zone-gen-row">
              <div className="fg">
                <label className="field-label">Floors</label>
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={floors}
                  onChange={(e) => setFloors(parseInt(e.target.value) || 1)}
                />
              </div>
              <div className="fg">
                <label className="field-label">Zones per floor</label>
                <input
                  type="number"
                  min={2}
                  max={8}
                  value={zonesPerFloor}
                  onChange={(e) => setZonesPerFloor(parseInt(e.target.value) || 2)}
                />
              </div>
              <button type="button" className="btn" onClick={handleGenZones}>
                Generate zones
              </button>
            </div>
            <div className="zone-chip-list">
              {zoneDraft.map((z, i) => (
                <div className="zone-chip" key={z.id}>
                  <span>{z.id}</span>
                  <input value={z.label} onChange={(e) => updateZoneLabel(i, e.target.value)} />
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="sec-title">
              <span className="n">3</span>Team dispatch — firefighter, zone, camera rig
            </div>
            {teamRows.map((row, i) => (
              <div className="team-row-form" key={i}>
                <input
                  placeholder="Firefighter name"
                  value={row.name}
                  onChange={(e) => updateTeamRow(i, { name: e.target.value })}
                />
                <select value={row.zone} onChange={(e) => updateTeamRow(i, { zone: e.target.value })}>
                  {zoneDraft.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.id} · {z.label}
                    </option>
                  ))}
                </select>
                <select
                  value={row.cam}
                  onChange={(e) => updateTeamRow(i, { cam: parseInt(e.target.value) })}
                >
                  <option value={1}>Cam 1</option>
                  <option value={2}>Cam 2</option>
                  <option value={3}>Cam 3</option>
                </select>
                <button type="button" className="rm-btn" onClick={() => removeTeamRow(i)} title="Remove">
                  ✕
                </button>
              </div>
            ))}
            <button type="button" className="add-row-btn" onClick={addTeamRow}>
              + Add firefighter
            </button>
          </div>

          {error && <p style={{ color: 'var(--unsafe)', fontSize: 12 }}>{error}</p>}
        </div>

        <div className="modal-foot">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn primary">
            Dispatch team & create incident
          </button>
        </div>
      </form>
    </div>
  );
}
