import { useIncident } from '../../state/IncidentContext';
import './TeamDeployment.css';

export function TeamDeployment() {
  const { incident } = useIncident();

  return (
    <div>
      <div className="crumbs">Operations / Team deployment</div>
      <div className="page-title-row">
        <div>
          <h1>Team deployment</h1>
          <p>Roster status across active field units and command post staff.</p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-body">
          {!incident ? (
            <p style={{ color: 'var(--text-mid)', fontSize: 12.5 }}>
              No team currently dispatched. Team assignments appear here once an emergency is logged.
            </p>
          ) : (
            <div className="roster-grid">
              {incident.teams.map((t) => {
                const initials = t.name
                  .split(' ')
                  .map((w) => w[0])
                  .join('')
                  .slice(0, 2)
                  .toUpperCase();
                return (
                  <div className="roster-card" key={t.name + t.zone}>
                    <div className="roster-card-head">
                      <div className="avatar">{initials}</div>
                      <div>
                        <div className="roster-name">{t.name}</div>
                        <div className="roster-cam">
                          Camera {t.cam} · Thermal + RGB
                        </div>
                      </div>
                    </div>
                    <div className="roster-zone">Assigned zone: {t.zone}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
