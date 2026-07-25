export function TrainingSimulator() {
  return (
    <div>
      <div className="crumbs">Training / Simulation trainer</div>
      <div className="page-title-row">
        <div>
          <h1>Scenario-based training</h1>
          <p>Classify zones from real incident imagery, then compare your call against the model's output.</p>
        </div>
      </div>
      <div className="panel">
        <div className="panel-body placeholder-panel">
          Training scenarios are available between live incidents. Close the active incident to begin a simulation.
        </div>
      </div>
    </div>
  );
}
