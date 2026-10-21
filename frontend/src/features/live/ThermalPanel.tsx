import { useTranslation } from 'react-i18next';
import { useDetections, useThermalUploads } from '../../api/thermal';
import { DetectionViewer } from '../../components/DetectionViewer';
import { formatTime } from '../../lib/format';

/** Latest analysed thermal media (web upload or mobile sync) — the web never shows live
 * thermal video (SRS); this replaces the prototype's live thermal panel (HANDOFF §4.2). */
export function ThermalPanel({ incidentId }: { incidentId: string }) {
  const { t } = useTranslation();
  const uploads = useThermalUploads(incidentId);
  const latest = uploads.data?.find((u) => u.job?.status === 'done' || u.source === 'mobile_sync');
  const dets = useDetections(latest?.media_id);
  return (
    <div className="panel" data-testid="thermal-panel">
      <div className="panel-head">
        <h2>{t('live.thermal')}</h2>
        {latest && (
          <span className="meta">
            {t(`analysis.source.${latest.source}`)} · {latest.zone_code ?? '—'} ·{' '}
            {formatTime(latest.created_at)}
          </span>
        )}
      </div>
      <div className="panel-body">
        {latest ? (
          <DetectionViewer
            compact
            mediaId={latest.media_id}
            url={latest.url}
            kind={latest.kind}
            detections={dets.data ?? []}
          />
        ) : (
          <div className="feed-placeholder">{t('live.noThermal')}</div>
        )}
      </div>
    </div>
  );
}
