import './IncidentReports.css';

const ROWS = [
  {
    session: 'IV-2026-0411',
    location: 'Centaurus Mall, Islamabad',
    timestamp: '2026-07-24 21:05',
    humans: 0,
    status: 'Caution',
  },
  {
    session: 'IV-2026-0410',
    location: 'Rawalpindi Industrial Zone',
    timestamp: '2026-07-24 14:47',
    humans: 1,
    status: 'Caution',
  },
];

export function IncidentReports() {
  return (
    <div>
      <div className="crumbs">Operations / Incident reports</div>
      <div className="page-title-row">
        <div>
          <h1>Incident reports</h1>
          <p>Logged analysis sessions — timestamp, zone distribution, human count, model confidence.</p>
        </div>
        <button className="btn primary">Export PDF</button>
      </div>

      <div className="reports-table-wrap">
        <table className="reports-table">
          <thead>
            <tr>
              <th>Session</th>
              <th>Location</th>
              <th>Timestamp</th>
              <th>Humans</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.session}>
                <td>{r.session}</td>
                <td>{r.location}</td>
                <td>{r.timestamp}</td>
                <td>{r.humans}</td>
                <td>
                  <span className="status-pill">{r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
