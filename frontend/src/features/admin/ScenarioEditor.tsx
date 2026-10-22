import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '../../api/errors';
import {
  POSTURE_LABELS,
  ZONE_LABELS,
  uploadScenarioItem,
  useAdminScenario,
  useDeleteItem,
  useDeleteScenario,
  useRecompute,
  useSaveItem,
  useUpdateScenario,
  type AdminItem,
  type Box,
  type GroundTruth,
  type Point,
  type PostureLabel,
  type ScenarioIn,
  type ZoneLabel,
} from '../../api/training';
import { ConfirmDialog } from '../../components/Modal';
import { PageHeader } from '../../components/PageHeader';
import { errorMessage } from '../../i18n';
import { MediaStage } from '../trainer/MediaStage';
import { pick } from '../trainer/util';
import { AdminTabs } from './AdminTabs';
import { ScenarioFields } from './ScenarioFields';

type Tool = 'select' | 'polygon' | 'box';
const r4 = (v: number) => Math.round(v * 10000) / 10000;

function normalise(gt: Record<string, unknown>, kind: string): GroundTruth {
  return {
    type: (gt.type as GroundTruth['type']) ?? (kind === 'posture' ? 'posture' : 'zone'),
    regions: (gt.regions as GroundTruth['regions']) ?? [],
    people: (gt.people as GroundTruth['people']) ?? [],
    explanation_en: (gt.explanation_en as string) ?? '',
    explanation_ur: (gt.explanation_ur as string) ?? '',
    frame_s: (gt.frame_s as number | null) ?? null,
  };
}

function nextId(prefix: string, ids: string[]): string {
  const n = ids.map((i) => Number(i.replace(/^\D+/, '')) || 0);
  return `${prefix}${Math.max(0, ...n) + 1}`;
}

/** In-browser labelling tool (HANDOFF §9.6): grid cells or polygons for zone regions, dragged
 * boxes for people, a label each, explanations, and the labelled frame for videos. */
function Labeller({
  scenarioId,
  kind,
  item,
}: {
  scenarioId: string;
  kind: string;
  item: AdminItem;
}) {
  const { t } = useTranslation();
  const save = useSaveItem(scenarioId);
  const del = useDeleteItem(scenarioId);
  const [gt, setGt] = useState<GroundTruth>(() => normalise(item.ground_truth, kind));
  const [tool, setTool] = useState<Tool>('select');
  const [poly, setPoly] = useState<Point[]>([]);
  const [drag, setDrag] = useState<{ a: Point; b: Point } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [grid, setGrid] = useState({ rows: 2, cols: 2 });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);
  const dirty = JSON.stringify(gt) !== JSON.stringify(normalise(item.ground_truth, kind));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPoly([]);
        setDrag(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const zone = gt.type === 'zone';
  const ref = (item.reference_output ?? {}) as {
    regions?: Record<string, { status: string | null }>;
    people?: Record<string, { posture: string | null; detected: boolean }>;
  };
  const finishPolygon = () => {
    if (poly.length < 3) return;
    const id = nextId(
      'r',
      gt.regions.map((r) => r.id),
    );
    setGt({
      ...gt,
      regions: [
        ...gt.regions,
        { id, polygon: poly.map(([x, y]) => [r4(x), r4(y)] as Point), status: 'safe' },
      ],
    });
    setPoly([]);
    setSelected(id);
  };
  const onPointer = (k: 'down' | 'move' | 'up', p: Point) => {
    if (tool === 'polygon' && k === 'down') {
      const first = poly[0];
      if (first && poly.length >= 3 && Math.hypot(first[0] - p[0], first[1] - p[1]) < 0.02)
        finishPolygon();
      else setPoly([...poly, p]);
    }
    if (tool === 'box') {
      if (k === 'down') setDrag({ a: p, b: p });
      else if (k === 'move' && drag) setDrag({ ...drag, b: p });
      else if (k === 'up' && drag) {
        const [x1, x2] = [Math.min(drag.a[0], p[0]), Math.max(drag.a[0], p[0])];
        const [y1, y2] = [Math.min(drag.a[1], p[1]), Math.max(drag.a[1], p[1])];
        setDrag(null);
        if (x2 - x1 > 0.01 && y2 - y1 > 0.01) {
          const id = nextId(
            'p',
            gt.people.map((x) => x.id),
          );
          setGt({
            ...gt,
            people: [
              ...gt.people,
              { id, bbox: [r4(x1), r4(y1), r4(x2), r4(y2)] as Box, posture: 'standing' },
            ],
          });
          setSelected(id);
        }
      }
    }
  };
  const applyGrid = () => {
    const regions: GroundTruth['regions'] = [];
    for (let r = 0; r < grid.rows; r++)
      for (let c = 0; c < grid.cols; c++) {
        const [x0, y0, x1, y1] = [
          c / grid.cols,
          r / grid.rows,
          (c + 1) / grid.cols,
          (r + 1) / grid.rows,
        ].map(r4);
        regions.push({
          id: `r${regions.length + 1}`,
          polygon: [
            [x0, y0],
            [x1, y0],
            [x1, y1],
            [x0, y1],
          ],
          status: 'safe',
        });
      }
    setGt({ ...gt, regions });
  };

  const stageItem = {
    media_kind: item.media_kind,
    media_url: item.media_url,
    frame_s: gt.frame_s,
    regions: zone ? gt.regions : [],
    people: zone ? [] : gt.people,
  };
  const labels = Object.fromEntries(
    zone
      ? gt.regions.map((r) => [r.id, { text: t(`status.${r.status}`), tone: `ans-${r.status}` }])
      : gt.people.map((p) => [p.id, { text: t(`posture.${p.posture}`), tone: `ans-${p.posture}` }]),
  );
  const box = drag && {
    x: Math.min(drag.a[0], drag.b[0]),
    y: Math.min(drag.a[1], drag.b[1]),
    w: Math.abs(drag.a[0] - drag.b[0]),
    h: Math.abs(drag.a[1] - drag.b[1]),
  };

  return (
    <div className="labeller" data-testid="labeller">
      <div className="labeller-tools">
        <div className="seg" role="group" aria-label={t('admin.lab.type')}>
          {(['zone', 'posture'] as const).map((ty) => (
            <button
              key={ty}
              type="button"
              aria-pressed={gt.type === ty}
              onClick={() => setGt({ ...gt, type: ty })}
              data-type={ty}
            >
              {t(`trainer.kind.${ty}`)}
            </button>
          ))}
        </div>
        <div className="seg" role="group" aria-label={t('admin.lab.tool')}>
          <button type="button" aria-pressed={tool === 'select'} onClick={() => setTool('select')}>
            {t('admin.lab.select')}
          </button>
          {zone ? (
            <button
              type="button"
              aria-pressed={tool === 'polygon'}
              onClick={() => setTool('polygon')}
              data-testid="tool-polygon"
            >
              {t('admin.lab.polygon')}
            </button>
          ) : (
            <button
              type="button"
              aria-pressed={tool === 'box'}
              onClick={() => setTool('box')}
              data-testid="tool-box"
            >
              {t('admin.lab.box')}
            </button>
          )}
        </div>
        {zone && (
          <div className="grid-tool">
            <label>
              {t('admin.lab.rows')}
              <input
                type="number"
                min={1}
                max={6}
                value={grid.rows}
                onChange={(e) => setGrid({ ...grid, rows: Number(e.target.value) })}
              />
            </label>
            <label>
              {t('admin.lab.cols')}
              <input
                type="number"
                min={1}
                max={6}
                value={grid.cols}
                onChange={(e) => setGrid({ ...grid, cols: Number(e.target.value) })}
              />
            </label>
            <button type="button" className="btn" onClick={applyGrid} data-testid="apply-grid">
              {t('admin.lab.applyGrid')}
            </button>
          </div>
        )}
        {tool === 'polygon' && (
          <span className="muted small">
            {t('admin.lab.polygonHint')}{' '}
            <button
              type="button"
              className="btn"
              disabled={poly.length < 3}
              onClick={finishPolygon}
              data-testid="finish-polygon"
            >
              {t('admin.lab.finish')}
            </button>
          </span>
        )}
        {tool === 'box' && <span className="muted small">{t('admin.lab.boxHint')}</span>}
      </div>

      <div className="labeller-grid">
        <MediaStage
          item={stageItem}
          labels={labels}
          shapeClass={() => 'answered'}
          selectedId={selected}
          onSelect={tool === 'select' ? setSelected : undefined}
          onStagePointer={tool === 'select' ? undefined : onPointer}
          videoRef={(el) => (video.current = el)}
          testId="label-stage"
          overlay={
            <>
              {poly.length > 0 && (
                <polyline
                  className="draft"
                  points={poly.map((p) => p.join(',')).join(' ')}
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {box && (
                <rect
                  className="draft"
                  x={box.x}
                  y={box.y}
                  width={box.w}
                  height={box.h}
                  vectorEffect="non-scaling-stroke"
                />
              )}
            </>
          }
        />
        <div className="labeller-side">
          {item.media_kind === 'video' && (
            <p>
              <button
                type="button"
                className="btn"
                onClick={() =>
                  setGt({ ...gt, frame_s: Math.round((video.current?.currentTime ?? 0) * 10) / 10 })
                }
              >
                {t('admin.lab.useFrame')}
              </button>{' '}
              <span className="muted small">
                {t('trainer.labelledFrame', { t: (gt.frame_s ?? 0).toFixed(1) })}
              </span>
            </p>
          )}
          <ul className="target-list" data-testid="target-list">
            {zone
              ? gt.regions.map((r, i) => (
                  <li key={r.id} className={selected === r.id ? 'selected' : undefined}>
                    <button type="button" className="linklike" onClick={() => setSelected(r.id)}>
                      {t('trainer.region', { n: i + 1 })}
                    </button>
                    <select
                      value={r.status}
                      aria-label={t('trainer.region', { n: i + 1 })}
                      onChange={(e) =>
                        setGt({
                          ...gt,
                          regions: gt.regions.map((x) =>
                            x.id === r.id ? { ...x, status: e.target.value as ZoneLabel } : x,
                          ),
                        })
                      }
                    >
                      {ZONE_LABELS.map((l) => (
                        <option key={l} value={l}>
                          {t(`status.${l}`)}
                        </option>
                      ))}
                    </select>
                    <span className="muted small">
                      {t('trainer.view.model')}:{' '}
                      {ref.regions?.[r.id]
                        ? ref.regions[r.id].status
                          ? t(`status.${ref.regions[r.id].status}`)
                          : t('trainer.notAnalysable')
                        : '—'}
                    </span>
                    <button
                      type="button"
                      className="btn"
                      aria-label={t('admin.lab.remove')}
                      onClick={() =>
                        setGt({ ...gt, regions: gt.regions.filter((x) => x.id !== r.id) })
                      }
                    >
                      ✕
                    </button>
                  </li>
                ))
              : gt.people.map((p, i) => (
                  <li key={p.id} className={selected === p.id ? 'selected' : undefined}>
                    <button type="button" className="linklike" onClick={() => setSelected(p.id)}>
                      {t('trainer.person', { n: i + 1 })}
                    </button>
                    <select
                      value={p.posture}
                      aria-label={t('trainer.person', { n: i + 1 })}
                      onChange={(e) =>
                        setGt({
                          ...gt,
                          people: gt.people.map((x) =>
                            x.id === p.id ? { ...x, posture: e.target.value as PostureLabel } : x,
                          ),
                        })
                      }
                    >
                      {POSTURE_LABELS.map((l) => (
                        <option key={l} value={l}>
                          {t(`posture.${l}`)}
                        </option>
                      ))}
                    </select>
                    <span className="muted small">
                      {t('trainer.view.model')}:{' '}
                      {ref.people?.[p.id]?.posture
                        ? t(`posture.${ref.people[p.id].posture}`)
                        : t('trainer.noModel')}
                    </span>
                    <button
                      type="button"
                      className="btn"
                      aria-label={t('admin.lab.remove')}
                      onClick={() =>
                        setGt({ ...gt, people: gt.people.filter((x) => x.id !== p.id) })
                      }
                    >
                      ✕
                    </button>
                  </li>
                ))}
          </ul>
          {(zone ? gt.regions : gt.people).length === 0 && (
            <p className="muted small">{t('admin.lab.noTargets')}</p>
          )}
          <label>
            <span className="field-label">{t('admin.lab.explainEn')}</span>
            <textarea
              rows={3}
              dir="ltr"
              value={gt.explanation_en}
              onChange={(e) => setGt({ ...gt, explanation_en: e.target.value })}
            />
          </label>
          <label>
            <span className="field-label">{t('admin.lab.explainUr')}</span>
            <textarea
              rows={3}
              dir="rtl"
              lang="ur"
              value={gt.explanation_ur}
              onChange={(e) => setGt({ ...gt, explanation_ur: e.target.value })}
            />
          </label>
          <p className={item.usable ? 'ok-text small' : 'bad-text small'} data-testid="item-usable">
            {item.usable ? t('admin.lab.usable') : t('admin.lab.unusable')}
          </p>
          {msg && <p className="error-text">{msg}</p>}
          <div className="row-actions">
            <button type="button" className="btn danger" onClick={() => setConfirmDelete(true)}>
              {t('admin.lab.deleteItem')}
            </button>
            <button
              type="button"
              className="btn primary"
              disabled={!dirty || save.isPending}
              data-testid="save-item"
              onClick={() =>
                save.mutate(
                  { itemId: item.id, ground_truth: gt },
                  {
                    onSuccess: () => setMsg(null),
                    onError: (e) =>
                      setMsg(errorMessage(e instanceof ApiError ? e.code : undefined)),
                  },
                )
              }
            >
              {save.isPending ? t('admin.lab.saving') : t('admin.lab.save')}
            </button>
          </div>
        </div>
      </div>
      {confirmDelete && (
        <ConfirmDialog
          title={t('admin.lab.deleteItemTitle')}
          body={t('admin.lab.deleteItemBody')}
          confirmLabel={t('admin.lab.deleteItem')}
          busy={del.isPending}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() => del.mutate(item.id, { onSuccess: () => setConfirmDelete(false) })}
        />
      )}
    </div>
  );
}

export function ScenarioEditor() {
  const { t } = useTranslation();
  const { scenarioId } = useParams();
  const navigate = useNavigate();
  const q = useAdminScenario(scenarioId);
  const update = useUpdateScenario(scenarioId!);
  const delScenario = useDeleteScenario();
  const recompute = useRecompute(scenarioId!);
  const [fields, setFields] = useState<ScenarioIn | null>(null);
  const [itemId, setItemId] = useState<string | null>(null);
  const [upload, setUpload] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const sc = q.data;
  useEffect(() => {
    if (sc && !fields)
      setFields({
        title_en: sc.title_en,
        title_ur: sc.title_ur,
        description_en: sc.description_en ?? '',
        description_ur: sc.description_ur ?? '',
        difficulty: sc.difficulty,
        kind: sc.kind,
        is_active: sc.is_active,
      });
  }, [sc, fields]);
  useEffect(() => {
    if (sc && (!itemId || !sc.items.some((i) => i.id === itemId)))
      setItemId(sc.items[0]?.id ?? null);
  }, [sc, itemId]);

  if (q.isLoading || !fields) return <div className="loader">{t('common.loading')}</div>;
  if (!sc)
    return (
      <div className="empty-state">
        <Link to="/admin/scenarios">{t('common.back')}</Link>
      </div>
    );
  const item = sc.items.find((i) => i.id === itemId);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setNotice(null);
    setUpload(0);
    try {
      const it = await uploadScenarioItem(sc.id, file, setUpload);
      await q.refetch();
      setItemId(it.id);
    } catch (e) {
      setNotice(errorMessage(e instanceof ApiError ? e.code : undefined));
    } finally {
      setUpload(null);
    }
  };

  return (
    <>
      <PageHeader
        page="admin"
        actions={
          <div className="row-actions">
            <Link className="btn" to="/admin/scenarios">
              {t('common.back')}
            </Link>
            <button
              type="button"
              className="btn danger"
              onClick={() => setConfirmDelete(true)}
              data-testid="delete-scenario"
            >
              {t('admin.sc.delete')}
            </button>
          </div>
        }
      />
      <AdminTabs />
      {notice && (
        <div className="banner warn" role="status">
          {notice}
        </div>
      )}
      <section className="panel" data-testid="scenario-editor">
        <div className="panel-head">
          <h2>{pick(sc.title_en, sc.title_ur)}</h2>
          {sc.is_placeholder && <span className="tag warn">{t('trainer.placeholder')}</span>}
        </div>
        <div className="panel-body">
          <ScenarioFields value={fields} onChange={setFields} />
          <div className="row-actions">
            <button
              type="button"
              className="btn primary"
              disabled={update.isPending}
              onClick={() =>
                update.mutate(fields, { onSuccess: () => setNotice(t('common.saved')) })
              }
              data-testid="save-scenario"
            >
              {t('common.save')}
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>{t('admin.sc.items')}</h2>
          <span className="meta">
            {t('admin.sc.usableOf', { usable: sc.usable_count, total: sc.item_count })}
          </span>
        </div>
        <div className="panel-body">
          <div className="item-strip">
            {sc.items.map((it, i) => (
              <button
                key={it.id}
                type="button"
                className={`item-thumb${it.id === itemId ? ' selected' : ''}${it.usable ? '' : ' unusable'}`}
                onClick={() => setItemId(it.id)}
                aria-pressed={it.id === itemId}
                data-testid="item-thumb"
              >
                {it.media_kind === 'video' ? (
                  <span className="vid">▶</span>
                ) : (
                  <img src={it.media_url ?? undefined} alt="" />
                )}
                <span>
                  {i + 1}
                  {it.usable ? '' : ' ⚠'}
                </span>
              </button>
            ))}
            <label className="item-thumb add" data-testid="add-item">
              <input
                type="file"
                accept="image/jpeg,image/png,video/mp4,video/webm,video/quicktime"
                hidden
                onChange={(e) => void onFile(e.target.files?.[0])}
              />
              <span>
                {upload == null ? `+ ${t('admin.sc.addItem')}` : `${Math.round(upload * 100)}%`}
              </span>
            </label>
          </div>
          <p className="muted small">{t('admin.sc.itemsHint')}</p>
          <div className="row-actions">
            <button
              type="button"
              className="btn"
              disabled={recompute.isPending || !sc.items.length}
              data-testid="recompute"
              onClick={() =>
                recompute.mutate(undefined, {
                  onSuccess: (r) =>
                    setNotice(
                      t('admin.sc.recomputed', {
                        computed: r.computed,
                        skipped: r.skipped,
                        failed: r.failed,
                      }),
                    ),
                })
              }
            >
              {recompute.isPending ? t('admin.lab.saving') : t('admin.sc.recompute')}
            </button>
          </div>
        </div>
      </section>

      {item && (
        <Labeller
          key={`${item.id}:${JSON.stringify(item.ground_truth)}`}
          scenarioId={sc.id}
          kind={sc.kind}
          item={item}
        />
      )}

      {confirmDelete && (
        <ConfirmDialog
          title={t('admin.sc.deleteTitle', { title: pick(sc.title_en, sc.title_ur) })}
          body={t('admin.sc.deleteBody')}
          confirmLabel={t('admin.sc.delete')}
          busy={delScenario.isPending}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() =>
            delScenario.mutate(sc.id, {
              onSuccess: () => navigate('/admin/scenarios', { replace: true }),
            })
          }
        />
      )}
    </>
  );
}
