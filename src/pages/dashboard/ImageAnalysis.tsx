export function ImageAnalysis() {
  return (
    <div>
      <div className="crumbs">Operations / Image analysis</div>
      <div className="page-title-row">
        <div>
          <h1>Image analysis</h1>
          <p>Upload building imagery for offline zone segmentation and annotation.</p>
        </div>
        <button className="btn primary">Upload image</button>
      </div>
      <div className="panel">
        <div className="panel-body placeholder-panel">
          Drop an image here, or connect a session from Incident reports to analyze its frames.
        </div>
      </div>
    </div>
  );
}
