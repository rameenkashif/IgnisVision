import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import {
  OPEN,
  useAssign,
  useAssignmentHistory,
  useIncident,
  useIncidents,
  useMyAssignments,
  useResponders,
  useUnassign,
} from '../../api/incidents';
import type { IncidentDetail } from '../../api/types';
import { PageHeader } from '../../components/PageHeader';
import { formatDateTime } from '../../lib/format';
import { useAuth } from '../../stores/auth';
import { useIncidentStream, useStationStream } from '../../ws/hooks';

/** Team deployment: commanders assign/reassign (history kept), admins read, responders see
 * their own assignment only (HANDOFF §6). */
export function TeamPage() {
  const user = useAuth((s) => s.user)!;
  return (
    <>
      <PageHeader page="team" />
      {user.role === 'field_responder' ? (
        <MyAssignment />
      ) : (
        <TeamBoard canEdit={user.role === 'incident_commander'} />
      )}
    </>
  );
}

function MyAssignment() {
  const { t } = useTranslation();
  const mine = useMyAssignments();
  if (!mine.data?.length)
    return (
      <div className="empty-state">
        <p>{t('team.mineNone')}</p>
      </div>
    );
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t('team.mine')}</h2>
      </div>
      <div className="panel-body table-wrap">
        <table className="table" data-testid="my-assignments">
          <tbody>
            {mine.data.map((a) => (
              <tr key={a.id}>
                <td>{a.incident_code}</td>
                <td>{t(`incidentStatus.${a.incident_status}`)}</td>
                <td>{a.zone_code ?? '—'}</td>
                <td>{a.device_label ?? ''}</td>
                <td>{formatDateTime(a.assigned_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TeamBoard({ canEdit }: { canEdit: boolean }) {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  useStationStream(true);
  const open = useIncidents(OPEN);
  const items = open.data?.items ?? [];
  const selected = params.get('incident') ?? items[0]?.id;
  const incident = useIncident(items.some((i) => i.id === selected) ? selected : undefined);
  useIncidentStream(incident.data?.id);

  if (!open.isLoading && !items.length) {
    return (
      <div className="empty-state" data-testid="team-empty">
        <p>{t('team.noOpen')}</p>
      </div>
    );
  }
  return (
    <>
      {items.length > 1 && (
        <div className="incident-tabs" role="group" aria-label={t('team.chooseIncident')}>
          {items.map((i) => (
            <button
              key={i.id}
              type="button"
              aria-pressed={i.id === incident.data?.id}
              onClick={() => setParams({ incident: i.id }, { replace: true })}
            >
              {i.code}
            </button>
          ))}
        </div>
      )}
      {!canEdit && (
        <p className="muted" style={{ marginBlockEnd: 10 }}>
          {t('team.readOnly')}
        </p>
      )}
      {incident.data && <Board incident={incident.data} canEdit={canEdit} />}
    </>
  );
}

function Board({ incident, canEdit }: { incident: IncidentDetail; canEdit: boolean }) {
  const { t } = useTranslation();
  const history = useAssignmentHistory(incident.id);
  const responders = useResponders(canEdit);
  const assign = useAssign(incident.id);
  const unassign = useUnassign(incident.id);
  const [newUser, setNewUser] = useState('');
  const [newZone, setNewZone] = useState('');
  const zoneOptions = incident.zones.map((z) => (
    <option key={z.id} value={z.id}>
      {z.code}
      {z.label ? ` · ${z.label}` : ''}
    </option>
  ));

  return (
    <>
      <div className="panel" style={{ marginBlockEnd: 14 }}>
        <div className="panel-head">
          <h2>
            {t('team.current')} · {incident.code}
          </h2>
          <span className="meta">{incident.assignments.length}</span>
        </div>
        <div className="panel-body table-wrap">
          {incident.assignments.length === 0 ? (
            <p className="muted">{t('team.none')}</p>
          ) : (
            <table className="table" data-testid="current-assignments">
              <thead>
                <tr>
                  <th>{t('dispatch.responder')}</th>
                  <th>{t('dispatch.zone')}</th>
                  <th>{t('dispatch.device')}</th>
                  <th>{t('team.since')}</th>
                  {canEdit && <th />}
                </tr>
              </thead>
              <tbody>
                {incident.assignments.map((a) => (
                  <tr key={a.id} data-user={a.user.username}>
                    <td>{a.user.full_name}</td>
                    <td>
                      {canEdit ? (
                        <select
                          aria-label={t('team.reassign')}
                          value={a.zone_id ?? ''}
                          onChange={(e) =>
                            assign.mutate({
                              user_id: a.user.id,
                              zone_id: e.target.value || null,
                              device_label: a.device_label,
                            })
                          }
                        >
                          <option value="">{t('dispatch.noZone')}</option>
                          {zoneOptions}
                        </select>
                      ) : (
                        (a.zone_code ?? '—')
                      )}
                    </td>
                    <td>{a.device_label ?? ''}</td>
                    <td>{formatDateTime(a.assigned_at)}</td>
                    {canEdit && (
                      <td>
                        <button type="button" className="btn" onClick={() => unassign.mutate(a.id)}>
                          {t('team.unassign')}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {canEdit && (
            <form
              className="team-row-form"
              style={{ marginBlockStart: 12 }}
              onSubmit={(e) => {
                e.preventDefault();
                if (!newUser) return;
                assign.mutate(
                  { user_id: newUser, zone_id: newZone || null },
                  {
                    onSuccess: () => {
                      setNewUser('');
                      setNewZone('');
                    },
                  },
                );
              }}
            >
              <select
                aria-label={t('dispatch.responder')}
                value={newUser}
                onChange={(e) => setNewUser(e.target.value)}
              >
                <option value="">{t('team.add')}</option>
                {responders.data
                  ?.filter((r) => !incident.assignments.some((a) => a.user.id === r.id))
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.full_name}
                      {r.active_incident_code
                        ? ` (${t('dispatch.busy', { code: r.active_incident_code })})`
                        : ''}
                    </option>
                  ))}
              </select>
              <select
                aria-label={t('dispatch.zone')}
                value={newZone}
                onChange={(e) => setNewZone(e.target.value)}
              >
                <option value="">{t('dispatch.noZone')}</option>
                {zoneOptions}
              </select>
              <button type="submit" className="btn primary" disabled={!newUser || assign.isPending}>
                {t('team.assign')}
              </button>
            </form>
          )}
        </div>
      </div>
      <div className="panel">
        <div className="panel-head">
          <h2>{t('team.history')}</h2>
        </div>
        <div className="panel-body table-wrap">
          <table className="table" data-testid="assignment-history">
            <thead>
              <tr>
                <th>{t('dispatch.responder')}</th>
                <th>{t('dispatch.zone')}</th>
                <th>{t('team.since')}</th>
                <th>{t('team.until')}</th>
              </tr>
            </thead>
            <tbody>
              {history.data?.map((a) => (
                <tr key={a.id}>
                  <td>{a.user.full_name}</td>
                  <td>{a.zone_code ?? '—'}</td>
                  <td>{formatDateTime(a.assigned_at)}</td>
                  <td>{a.unassigned_at ? formatDateTime(a.unassigned_at) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
