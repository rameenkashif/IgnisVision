import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState, type DragEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useCaptureTargets } from '../../api/capture';
import { ApiError } from '../../api/errors';
import {
  thermalKeys,
  uploadThermal,
  useDetections,
  useJob,
  useThermalUploads,
} from '../../api/thermal';
import { DetectionViewer } from '../../components/DetectionViewer';
import { PageHeader } from '../../components/PageHeader';
import { errorMessage } from '../../i18n';
import { formatTime } from '../../lib/format';
import { useAuth } from '../../stores/auth';

const ACCEPT = 'image/jpeg,image/png,video/mp4,video/webm,video/quicktime';

type Item = {
  media_id: string;
  job_id?: string;
  name: string;
  kind: 'thermal_image' | 'thermal_video';
  url: string; // object URL for own uploads, signed URL for server-listed ones
  thumb?: string;
  zone_code?: string | null;
  source?: string;
  created_at?: string;
};

/** Thermal & image analysis (HANDOFF §11): upload → job progress → boxes, posture, RPI. */
export function AnalysisPage() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const isCommander = user.role === 'incident_commander';
  const qc = useQueryClient();
  const targets = useCaptureTargets();
  const [incidentId, setIncidentId] = useState('');
  const [zoneId, setZoneId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [over, setOver] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mine, setMine] = useState<Item[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const list = targets.data ?? [];
  const target = list.find((x) => x.incident.id === incidentId) ?? list[0];
  const server = useThermalUploads(target?.incident.id, isCommander);

  useEffect(() => () => mine.forEach((m) => URL.revokeObjectURL(m.url)), []); // eslint-disable-line react-hooks/exhaustive-deps

  const serverItems: Item[] = (server.data ?? []).map((u) => ({
    media_id: u.media_id,
    job_id: u.job?.id,
    name: `${u.kind === 'thermal_video' ? '🎞' : '🖼'} ${formatTime(u.created_at, true)}`,
    kind: u.kind,
    url: u.url,
    thumb: u.thumbnail_url,
    zone_code: u.zone_code,
    source: u.source,
    created_at: u.created_at,
  }));
  const items: Item[] = isCommander ? serverItems : mine;
  const current = items.find((i) => i.media_id === selected) ?? items[0];

  function pick(f: File | undefined | null) {
    setError(null);
    if (f && !ACCEPT.split(',').includes(f.type)) {
      setError(errorMessage('unsupported_media_type'));
      return;
    }
    setFile(f ?? null);
  }

  async function upload() {
    if (!file || !target) return;
    setError(null);
    setProgress(0);
    try {
      const res = await uploadThermal(target.incident.id, file, zoneId || null, setProgress);
      const item: Item = {
        media_id: res.media_id,
        job_id: res.job_id,
        name: file.name,
        kind: file.type.startsWith('video/') ? 'thermal_video' : 'thermal_image',
        url: URL.createObjectURL(file),
        zone_code: target.zones.find((z) => z.id === zoneId)?.code ?? null,
        source: 'web_upload',
      };
      setMine((m) => [item, ...m]);
      setSelected(res.media_id);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      void qc.invalidateQueries({ queryKey: thermalKeys.uploads(target.incident.id) });
    } catch (e) {
      setError(errorMessage(e instanceof ApiError ? e.code : undefined));
    } finally {
      setProgress(null);
    }
  }

  if (!targets.isLoading && !list.length) {
    return (
      <>
        <PageHeader page="analysis" />
        <div className="empty-state" data-testid="analysis-empty">
          <p>{t('analysis.noIncident')}</p>
        </div>
      </>
    );
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    pick(e.dataTransfer.files?.[0]);
  };

  return (
    <div data-testid="analysis-page">
      <PageHeader page="analysis" />
      <div className="analysis-grid">
        <div className="panel">
          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {list.length > 1 && (
              <label>
                <span className="field-label">{t('capture.incident')}</span>
                <select
                  value={target?.incident.id ?? ''}
                  onChange={(e) => {
                    setIncidentId(e.target.value);
                    setZoneId('');
                  }}
                >
                  {list.map((x) => (
                    <option key={x.incident.id} value={x.incident.id}>
                      {x.incident.code} · {x.incident.address}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              <span className="field-label">{t('analysis.zoneOptional')}</span>
              <select
                value={zoneId}
                onChange={(e) => setZoneId(e.target.value)}
                data-testid="analysis-zone"
              >
                <option value="">{t('analysis.noZone')}</option>
                {target?.zones.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.assigned_to_me ? '★ ' : ''}
                    {z.code}
                    {z.label ? ` · ${z.label}` : ''}
                  </option>
                ))}
              </select>
            </label>
            <div
              className={`file-drop${over ? ' over' : ''}`}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={onDrop}
              onClick={() => inputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
            >
              <div>{t('analysis.drop')}</div>
              <div className="hint">{t('analysis.formats')}</div>
              {file && <div className="file-name">{file.name}</div>}
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                hidden
                data-testid="analysis-file"
                onChange={(e) => pick(e.target.files?.[0])}
              />
            </div>
            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}
            {progress !== null && (
              <div>
                <div className="hint">
                  {t('analysis.uploading', { pct: Math.round(progress * 100) })}
                </div>
                <div className="progress">
                  <span style={{ width: `${progress * 100}%` }} />
                </div>
              </div>
            )}
            <button
              type="button"
              className="btn primary"
              disabled={!file || progress !== null}
              onClick={() => void upload()}
              data-testid="analysis-upload"
            >
              {t('analysis.upload')}
            </button>

            <div className="field-label" style={{ marginBlockStart: 6 }}>
              {t('analysis.uploads')}
            </div>
            {items.length === 0 ? (
              <p className="muted">{t('analysis.noUploads')}</p>
            ) : (
              <ul className="upload-list" data-testid="upload-list">
                {items.map((i) => (
                  <li key={i.media_id}>
                    <UploadRow
                      item={i}
                      selected={i.media_id === current?.media_id}
                      onSelect={() => setSelected(i.media_id)}
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>{t('analysis.viewer')}</h2>
          </div>
          <div className="panel-body">
            {current ? (
              <Viewer item={current} />
            ) : (
              <p className="muted">{t('analysis.noUploads')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function UploadRow({
  item,
  selected,
  onSelect,
}: {
  item: Item;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  const job = useJob(item.job_id);
  const s = job.data?.status;
  const label =
    s === 'done'
      ? t('analysis.done')
      : s === 'failed'
        ? t('analysis.failed')
        : s === 'running'
          ? t('analysis.running', { pct: Math.round((job.data?.progress ?? 0) * 100) })
          : t('analysis.queued');
  return (
    <button
      type="button"
      className="upload-item"
      aria-pressed={selected}
      onClick={onSelect}
      data-job-status={s ?? 'queued'}
    >
      {item.thumb ? (
        <img src={item.thumb} alt="" />
      ) : (
        <span style={{ width: 56, textAlign: 'center' }}>
          {item.kind === 'thermal_video' ? '🎞' : '🖼'}
        </span>
      )}
      <span className="meta">
        <span
          style={{
            color: 'var(--text-hi)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {item.name}
        </span>
        <span>
          {item.zone_code ?? '—'} · {t(`analysis.source.${item.source ?? 'web_upload'}`)}
        </span>
        <span className={s === 'failed' ? 'error-text' : undefined}>
          {item.job_id ? label : t('analysis.done')}
        </span>
        {s === 'running' && (
          <span className="progress">
            <span style={{ width: `${(job.data?.progress ?? 0) * 100}%` }} />
          </span>
        )}
      </span>
    </button>
  );
}

function Viewer({ item }: { item: Item }) {
  const job = useJob(item.job_id);
  const ready = !item.job_id || job.data?.status === 'done';
  const dets = useDetections(item.media_id, ready);
  return (
    <DetectionViewer
      mediaId={item.media_id}
      url={item.url}
      kind={item.kind}
      ready={ready}
      detections={ready ? (dets.data ?? []) : []}
    />
  );
}
