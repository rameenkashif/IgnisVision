import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.ml import runtime
from app.models import Incident, IncidentReport, MediaAsset, User
from app.reports.pdf import render_pdf
from app.schemas.reports import ReportFrame, ReportOut
from app.services import incidents as incidents_svc
from app.services import reports as reports_svc
from app.services.media import media_url
from app.services.video import frames_prefix
from app.storage.backend import get_storage

router = APIRouter(tags=["reports"])
Reader = Annotated[User, Depends(require_roles("incident_commander", "admin"))]
Commander = Annotated[User, Depends(require_roles("incident_commander"))]


async def _report(db: DB, inc: Incident, user: User) -> IncidentReport:
    if inc.status != "closed":
        raise AppError(409, "incident_not_closed")
    report = (
        await db.execute(select(IncidentReport).where(IncidentReport.incident_id == inc.id))
    ).scalar_one_or_none()
    if report is None:  # e.g. closed mobile-sync incidents or pre-existing data
        report = await reports_svc.compile_and_store(db, inc, user.id)
        await db.commit()
    return report


def _frame_url(f: dict) -> str | None:
    if f["kind"] == "thermal" and f.get("frame_index") is not None:
        return media_url(f["media_id"], f"/frames/{f['frame_index']}")
    return media_url(f["media_id"])


def _out(report: IncidentReport) -> ReportOut:
    s = report.stats
    return ReportOut(
        incident_id=report.incident_id,
        generated_at=report.generated_at,
        generated_by=report.generated_by,
        narrative_en=s["narrative"]["en"],
        narrative_ur=s["narrative"]["ur"],
        narrative_source=s["narrative"]["source"],
        stats={k: v for k, v in s.items() if k not in ("narrative", "pdfs")},
        frames=[ReportFrame(**{k: f.get(k) for k in ReportFrame.model_fields if k != "url"},
                            url=_frame_url(f)) for f in s.get("frames", [])],
    )  # fmt: skip


@router.get("/incidents/{incident_id}/report", response_model=ReportOut)
async def get_report(incident_id: uuid.UUID, user: Reader, db: DB) -> ReportOut:
    inc = await incidents_svc.get_incident(db, incident_id)
    return _out(await _report(db, inc, user))


@router.post("/incidents/{incident_id}/report/regenerate", response_model=ReportOut)
async def regenerate_report(incident_id: uuid.UUID, user: Commander, db: DB) -> ReportOut:
    inc = await incidents_svc.get_incident(db, incident_id)
    if inc.status != "closed":
        raise AppError(409, "incident_not_closed")
    report = await reports_svc.compile_and_store(db, inc, user.id)
    await db.commit()
    reports_svc.schedule_enrichment(report.id)
    return _out(report)


async def _frame_paths(db: DB, frames: list[dict]) -> list[tuple[dict, str]]:
    storage, out = get_storage(), []
    for f in frames:
        media = await db.get(MediaAsset, uuid.UUID(f["media_id"]))
        if media is None:
            continue
        path = storage.path(media.storage_key)
        if (
            f["kind"] == "thermal"
            and media.kind == "thermal_video"
            and f.get("frame_index") is not None
        ):
            folder = storage.path(frames_prefix(media.storage_key))
            match = next(iter(sorted(folder.glob(f"{f['frame_index']:07d}_*.jpg"))), None)
            if match is None:
                continue
            path = match
        if path.exists():
            out.append((f, path.as_uri()))
    return out


@router.get("/incidents/{incident_id}/report.pdf", response_class=Response)
async def report_pdf(
    incident_id: uuid.UUID,
    user: Reader,
    db: DB,
    lang: Literal["en", "ur"] = Query(default="en"),
) -> Response:
    """Rendered on first request per language and cached until the report is regenerated."""
    inc = await incidents_svc.get_incident(db, incident_id)
    report = await _report(db, inc, user)
    stats = dict(report.stats)
    storage = get_storage()
    cached = stats.get("pdfs", {}).get(lang)
    asset = await db.get(MediaAsset, uuid.UUID(cached)) if cached else None
    if asset is None or not storage.path(asset.storage_key).exists():
        frames = await _frame_paths(db, stats.get("frames", []))
        data = await runtime.run(render_pdf, stats, lang, frames, report.generated_at)
        key = f"reports/{inc.id}/{inc.code}-{lang}-{report.generated_at:%Y%m%dT%H%M%S}.pdf"
        storage.save(key, data)
        asset = MediaAsset(
            incident_id=inc.id, kind="report_pdf", storage_key=key, mime="application/pdf",
            bytes=len(data), uploaded_by=user.id, source="web_upload",
        )  # fmt: skip
        db.add(asset)
        await db.flush()
        stats["pdfs"] = {**stats.get("pdfs", {}), lang: str(asset.id)}
        report.stats = stats
        if lang == "en":
            report.pdf_media_id = asset.id
        await db.commit()
    data = storage.path(asset.storage_key).read_bytes()
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inc.code}-report-{lang}.pdf"'},
    )
