import './Settings.css';

export function Settings() {
  return (
    <div>
      <div className="crumbs">System / Settings</div>
      <div className="page-title-row">
        <div>
          <h1>Settings</h1>
          <p>Console preferences and alert behavior.</p>
        </div>
      </div>
      <div className="panel">
        <div className="panel-body">
          <div className="settings-row">
            <span>Sound alerts on critical reclassification</span>
            <span style={{ color: 'var(--safe)', fontFamily: 'var(--font-mono)' }}>On</span>
          </div>
          <div className="settings-row last">
            <span>Evacuation threshold (safe + caution %)</span>
            <span style={{ color: 'var(--text-mid)', fontFamily: 'var(--font-mono)' }}>40%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
