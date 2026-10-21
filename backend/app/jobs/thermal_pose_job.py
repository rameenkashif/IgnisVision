"""Thermal upload analysis (HANDOFF §9.3): image/video → frames (2 fps) → pose detector →
tracking → RPI → detections + victims → live events."""

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.db.engine import SessionLocal
from app.events.bus import bus, incident_channel
from app.ml import runtime
from app.ml.registry import get_models
from app.models import AnalysisJob, Incident, MediaAsset, ThermalDetection, Victim, Zone
from app.services import incidents as incidents_svc
from app.services import rpi as rpi_svc
from app.services import settings as settings_svc
from app.services import victims as victims_svc
from app.services.alerts import publish_alert
from app.services.tracking import Tracker
from app.services.video import VideoSampler, frame_jpeg, frames_prefix, read_image
from app.storage.backend import get_storage

log = logging.getLogger(__name__)
PROGRESS_EVERY_S = 0.5


async def _progress(job: AnalysisJob, incident_id: uuid.UUID) -> None:
    await bus.publish(
        incident_channel(incident_id),
        {"type": "job.progress", "job_id": str(job.id), "media_id": str(job.media_id),
         "status": job.status, "progress": round(job.progress, 3)},
    )  # fmt: skip


async def run_thermal_pose_job(job_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
        media = await db.get(MediaAsset, job.media_id)
        inc = await db.get(Incident, media.incident_id)
        models = get_models()
        values = await settings_svc.load_all(db)
        zone = await db.get(Zone, media.zone_id) if media.zone_id else None
        env_risk = None
        if zone:
            status, _ = incidents_svc.effective_status(
                zone, datetime.now(UTC), int(values["stale_zone_seconds"])
            )
            env_risk = rpi_svc.env_risk_from_zone(status)

        # Re-run after a restart: start clean (detections/victims of this media only).
        await db.execute(delete(ThermalDetection).where(ThermalDetection.media_id == media.id))
        await db.execute(delete(Victim).where(Victim.track_key.like(f"{media.id}:%")))
        job.status, job.progress, job.error = "running", 0.0, None
        job.started_at, job.finished_at = datetime.now(UTC), None
        job.model_name, job.model_version = models.pose.name, models.pose.version
        await db.commit()
        await _progress(job, inc.id)

        path = str(get_storage().path(media.storage_key))
        is_video = media.kind == "thermal_video"
        sampler = None
        try:
            if is_video:
                sampler = await runtime.run(VideoSampler, path)
                total = sampler.expected_samples
            else:
                total = 1
            tracker = Tracker(confirm_after=2 if is_video else 1)
            observations: dict[int, ThermalDetection] = {}  # obs id → row
            victims: dict[int, Victim] = {}  # track id → row
            done, last_push, t0 = 0, 0.0, time.perf_counter()
            base_time = media.created_at

            while True:
                if is_video:
                    sample = await runtime.run(sampler.next)
                    if sample is None:
                        break
                    frame_index, ts_ms, rgb = sample
                    # Keep the analysed frame: the viewer shows exactly what the model saw, and
                    # it plays in every browser whatever the upload's codec.
                    jpg = await runtime.run(frame_jpeg, rgb)
                    get_storage().save(
                        f"{frames_prefix(media.storage_key)}/{frame_index:07d}_{ts_ms}.jpg", jpg
                    )
                else:
                    if done:
                        break
                    frame_index, ts_ms = 0, 0
                    rgb = await runtime.run(read_image, path)

                people = await runtime.run(models.pose.predict, rgb)
                rows: list[ThermalDetection] = []
                for p in people:
                    r = rpi_svc.compute(
                        posture=p.posture, posture_confidence=p.posture_confidence,
                        detection_confidence=p.detection_confidence, env_risk=env_risk,
                        settings=values,
                    )  # fmt: skip
                    rows.append(
                        ThermalDetection(
                            incident_id=inc.id, zone_id=media.zone_id, media_id=media.id,
                            analysis_job_id=job.id, frame_index=frame_index, timestamp_ms=ts_ms,
                            bbox=list(p.bbox),
                            keypoints=[list(k) for k in p.keypoints] if p.keypoints else None,
                            posture=p.posture, posture_confidence=p.posture_confidence,
                            low_confidence=r.low_confidence,
                            detection_confidence=p.detection_confidence, env_risk=env_risk,
                            rpi_score=r.score, rpi_band=r.band, source="web_upload",
                            model_versions=models.versions(),
                            detected_at=base_time + timedelta(milliseconds=ts_ms),
                        )
                    )  # fmt: skip
                ids = list(range(len(observations), len(observations) + len(rows)))
                track_ids = tracker.update([tuple(r.bbox) for r in rows], ids)
                for oid, row, tid in zip(ids, rows, track_ids, strict=True):
                    row.track_id = tid
                    observations[oid] = row
                    db.add(row)
                await db.flush()

                # Upsert confirmed people seen in this sample (pushed live as we go).
                touched, new_alerts = [], []
                for t in tracker.confirmed():
                    if (
                        not t.observations
                        or observations[t.observations[-1]].frame_index != frame_index
                    ):
                        continue
                    v, alert = await victims_svc.upsert_track(
                        db, incident_id=inc.id, zone_id=media.zone_id,
                        zone_code=zone.code if zone else None, track_key=f"{media.id}:{t.id}",
                        observations=[observations[o] for o in t.observations],
                        source="web_upload", existing=victims.get(t.id),
                    )  # fmt: skip
                    victims[t.id] = v
                    touched.append(v)
                    if alert:
                        new_alerts.append(alert)

                done += 1
                job.progress = min(0.99, done / total)
                await db.commit()
                for v in touched:
                    await victims_svc.publish(db, v)
                for a in new_alerts:
                    await publish_alert(a)
                if time.perf_counter() - last_push > PROGRESS_EVERY_S:
                    last_push = time.perf_counter()
                    await _progress(job, inc.id)

            job.status, job.progress = "done", 1.0
            job.finished_at = datetime.now(UTC)
            if is_video and sampler.duration_s:
                media.duration_s = sampler.duration_s
            await db.commit()
            log.info(
                "thermal job %s: %d samples, %d detections, %d people in %.2fs",
                job.id, done, len(observations), len(victims), time.perf_counter() - t0,
            )  # fmt: skip
        except Exception as e:
            await db.rollback()
            job = await db.get(AnalysisJob, job_id)
            job.status, job.error = "failed", str(e)[:500] or e.__class__.__name__
            job.finished_at = datetime.now(UTC)
            await db.commit()
            log.exception("thermal job %s failed", job_id)
        finally:
            if sampler:
                sampler.close()
        await _progress(job, inc.id)
        await incidents_svc.publish_incident(db, inc)
