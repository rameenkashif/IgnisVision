import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import exists, func, select

from app.core.deps import DB, CurrentUser, bearer_user, require_roles
from app.core.errors import AppError
from app.jobs.queue import get_queue
from app.ml import runtime
from app.models import (
    AnalysisJob,
    Incident,
    MediaAsset,
    TeamAssignment,
    ThermalDetection,
    User,
    Victim,
    Zone,
)
from app.schemas.thermal import (
    DetectionOut,
    JobOut,
    SampleFrame,
    ThermalUploadOut,
    UploadAccepted,
    VictimOut,
    VictimUpdate,
)
from app.services import incidents as incidents_svc
from app.services import victims as victims_svc
from app.services.media import media_url, signature_valid
from app.services.video import VideoSampler, frames_prefix, probe_image, thumbnail_jpeg
from app.storage.backend import get_storage

router = APIRouter(tags=["thermal"])
Uploader = Annotated[User, Depends(require_roles("incident_commander", "field_responder"))]
Reader = Annotated[User, Depends(require_roles("incident_commander", "admin"))]
Commander = Annotated[User, Depends(require_roles("incident_commander"))]
JobViewer = Annotated[
    User, Depends(require_roles("incident_commander", "field_responder", "admin"))
]

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024


async def _may_use_incident(db: DB, user: User, inc: Incident) -> bool:
    if user.role in ("incident_commander", "admin"):
        return True
    if user.role != "field_responder":
        return False
    if inc.status == "active":
        return True
    q = select(
        exists().where(
            TeamAssignment.incident_id == inc.id,
            TeamAssignment.user_id == user.id,
            TeamAssignment.unassigned_at.is_(None),
        )
    )
    return bool((await db.execute(q)).scalar())


@router.post(
    "/incidents/{incident_id}/thermal-uploads", response_model=UploadAccepted, status_code=202
)
async def upload_thermal(
    incident_id: uuid.UUID,
    user: Uploader,
    db: DB,
    file: Annotated[
        UploadFile, File(description="Thermal image (JPEG/PNG) or video (MP4/WebM/MOV)")
    ],
    zone_id: Annotated[uuid.UUID | None, Form()] = None,
) -> UploadAccepted:
    """Accepts the file, queues analysis and returns immediately (poll GET /jobs/{id} or watch
    job.progress / victim.upserted on the incident channel)."""
    inc = await incidents_svc.get_incident(db, incident_id)
    if inc.status == "closed":
        raise AppError(409, "incident_closed")
    if not await _may_use_incident(db, user, inc):
        raise AppError(403, "forbidden")
    if zone_id is not None:
        zone = await db.get(Zone, zone_id)
        if zone is None or zone.incident_id != inc.id:
            raise AppError(422, "zone_not_in_incident")
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    if ctype in IMAGE_TYPES:
        kind, ext, limit = "thermal_image", IMAGE_TYPES[ctype], MAX_IMAGE_BYTES
    elif ctype in VIDEO_TYPES:
        kind, ext, limit = "thermal_video", VIDEO_TYPES[ctype], MAX_VIDEO_BYTES
    else:
        raise AppError(415, "unsupported_media_type", {"type": ctype})

    media_id = uuid.uuid4()
    key = f"incidents/{inc.id}/thermal/{media_id}{ext}"
    storage = get_storage()
    try:
        size, sha = await runtime.run(storage.save_stream, key, file.file, limit)
    except ValueError as e:
        raise AppError(413, "file_too_large", {"max_mb": limit // (1024 * 1024)}) from e
    path = str(storage.path(key))
    width = height = duration = None
    try:
        if kind == "thermal_image":
            width, height = await runtime.run(probe_image, path)
        else:
            sampler = await runtime.run(VideoSampler, path)
            width, height, duration = sampler.width, sampler.height, sampler.duration_s
            sampler.close()
    except Exception as e:
        storage.delete(key)
        raise AppError(422, "unreadable_media") from e

    asset = MediaAsset(
        id=media_id, incident_id=inc.id, zone_id=zone_id, kind=kind, storage_key=key, mime=ctype,
        bytes=size, width=width, height=height, duration_s=duration, sha256=sha,
        uploaded_by=user.id, source="web_upload",
    )  # fmt: skip
    db.add(asset)
    await db.flush()  # media row first: no ORM relationship orders these inserts
    job = AnalysisJob(media_id=media_id, job_type="thermal_pose")
    db.add(job)
    await db.commit()
    await get_queue().enqueue(job.id)
    return UploadAccepted(media_id=media_id, job_id=job.id)


@router.get("/incidents/{incident_id}/thermal-uploads", response_model=list[ThermalUploadOut])
async def list_thermal_uploads(incident_id: uuid.UUID, _: Reader, db: DB) -> list[ThermalUploadOut]:
    await incidents_svc.get_incident(db, incident_id)
    assets = (
        (
            await db.execute(
                select(MediaAsset)
                .where(
                    MediaAsset.incident_id == incident_id,
                    MediaAsset.kind.in_(("thermal_image", "thermal_video")),
                )
                .order_by(MediaAsset.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out = []
    for a in assets:
        job = (
            await db.execute(
                select(AnalysisJob)
                .where(AnalysisJob.media_id == a.id)
                .order_by(AnalysisJob.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        n_det = (
            await db.execute(select(func.count()).where(ThermalDetection.media_id == a.id))
        ).scalar_one()
        n_people = (
            await db.execute(select(func.count()).where(Victim.track_key.like(f"{a.id}:%")))
        ).scalar_one()
        zone = await db.get(Zone, a.zone_id) if a.zone_id else None
        out.append(
            ThermalUploadOut(
                media_id=a.id, kind=a.kind, source=a.source, zone_id=a.zone_id,
                zone_code=zone.code if zone else None, created_at=a.created_at,
                url=media_url(a.id), thumbnail_url=media_url(a.id, "/thumbnail"),
                duration_s=a.duration_s, width=a.width, height=a.height,
                job=JobOut.model_validate(job) if job else None, detections=n_det,
                people=n_people,
            )
        )  # fmt: skip
    return out


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, _: JobViewer, db: DB) -> AnalysisJob:
    job = await db.get(AnalysisJob, job_id)
    if job is None:
        raise AppError(404, "job_not_found")
    return job


@router.get("/media/{media_id}/detections", response_model=list[DetectionOut])
async def media_detections(
    media_id: uuid.UUID, user: CurrentUser, db: DB
) -> list[ThermalDetection]:
    asset = await db.get(MediaAsset, media_id)
    if asset is None or asset.incident_id is None:
        raise AppError(404, "media_not_found")
    inc = await db.get(Incident, asset.incident_id)
    if not await _may_use_incident(db, user, inc):
        raise AppError(403, "forbidden")
    rows = await db.execute(
        select(ThermalDetection)
        .where(ThermalDetection.media_id == media_id)
        .order_by(ThermalDetection.frame_index, ThermalDetection.track_id)
    )
    out = []
    for d in rows.scalars():
        item = DetectionOut.model_validate(d)
        if asset.kind == "thermal_video" and d.frame_index is not None:
            item.frame_url = media_url(media_id, f"/frames/{d.frame_index}")
        out.append(item)
    return out


def _sample_frames(asset: MediaAsset) -> list[tuple[int, int, str]]:
    folder = get_storage().path(frames_prefix(asset.storage_key))
    if not folder.exists():
        return []
    out = []
    for f in sorted(folder.glob("*.jpg")):
        idx, _, ms = f.stem.partition("_")
        out.append((int(idx), int(ms), f.name))
    return out


@router.get("/media/{media_id}/frames", response_model=list[SampleFrame])
async def media_frames(media_id: uuid.UUID, user: CurrentUser, db: DB) -> list[SampleFrame]:
    """The 2 fps samples a video was analysed on (empty for images)."""
    asset = await db.get(MediaAsset, media_id)
    if asset is None or asset.incident_id is None:
        raise AppError(404, "media_not_found")
    if not await _may_use_incident(db, user, await db.get(Incident, asset.incident_id)):
        raise AppError(403, "forbidden")
    return [
        SampleFrame(frame_index=i, timestamp_ms=ms, url=media_url(media_id, f"/frames/{i}"))
        for i, ms, _ in _sample_frames(asset)
    ]


@router.get("/media/{media_id}/frames/{frame_index}", response_class=Response)
async def media_frame(
    media_id: uuid.UUID,
    frame_index: int,
    request: Request,
    db: DB,
    exp: int | None = None,
    sig: str | None = None,
) -> Response:
    asset = await db.get(MediaAsset, media_id)
    if asset is None:
        raise AppError(404, "media_not_found")
    if not signature_valid(media_id, exp, sig):
        user = await bearer_user(request, db)
        inc = await db.get(Incident, asset.incident_id) if asset.incident_id else None
        if inc is not None and not await _may_use_incident(db, user, inc):
            raise AppError(403, "forbidden")
    match = next((n for i, _, n in _sample_frames(asset) if i == frame_index), None)
    if match is None:
        raise AppError(404, "frame_not_found")
    path = get_storage().path(f"{frames_prefix(asset.storage_key)}/{match}")
    return Response(
        path.read_bytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/media/{media_id}/thumbnail", response_class=Response)
async def media_thumbnail(
    media_id: uuid.UUID, request: Request, db: DB, exp: int | None = None, sig: str | None = None
) -> Response:
    asset = await db.get(MediaAsset, media_id)
    if asset is None:
        raise AppError(404, "media_not_found")
    if not signature_valid(media_id, exp, sig):
        user = await bearer_user(request, db)
        inc = await db.get(Incident, asset.incident_id) if asset.incident_id else None
        if inc is not None and not await _may_use_incident(db, user, inc):
            raise AppError(403, "forbidden")
    storage = get_storage()
    thumb_key = f"{asset.storage_key}.thumb.jpg"
    thumb = storage.path(thumb_key)
    if not thumb.exists():
        data = await runtime.run(
            thumbnail_jpeg, str(storage.path(asset.storage_key)), asset.mime.startswith("video/")
        )
        storage.save(thumb_key, data)
    return Response(
        thumb.read_bytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=600"},
    )


@router.get("/incidents/{incident_id}/victims", response_model=list[VictimOut])
async def list_victims(incident_id: uuid.UUID, _: Reader, db: DB) -> list[VictimOut]:
    """Ranked by Rescue Priority Index (highest first); rescued and false positives last."""
    await incidents_svc.get_incident(db, incident_id)
    return await victims_svc.ranked(db, incident_id)


@router.patch("/victims/{victim_id}", response_model=VictimOut)
async def update_victim(
    victim_id: uuid.UUID, body: VictimUpdate, _: Commander, db: DB
) -> VictimOut:
    v = await db.get(Victim, victim_id)
    if v is None:
        raise AppError(404, "victim_not_found")
    inc = await incidents_svc.get_incident(db, v.incident_id)
    v.status = body.status
    await db.commit()
    await victims_svc.publish(db, v)
    await incidents_svc.publish_incident(db, inc)
    return await victims_svc.victim_out(db, v)
