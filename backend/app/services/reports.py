"""Incident report (HANDOFF §8.5, SRS §4.7 REQ-4): compiled when an incident closes, stored as
structured stats + a narrative (template, or LLM when enabled), rendered to PDF on demand."""

import asyncio
import json
import logging
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.engine import SessionLocal
from app.llm.base import LLMUnavailable
from app.llm.registry import get_llm
from app.models import (
    Alert,
    AnalysisJob,
    CaptureSession,
    Floor,
    Incident,
    IncidentReport,
    MediaAsset,
    TeamAssignment,
    ThermalDetection,
    User,
    Zone,
    ZoneAssessment,
)
from app.services import settings as settings_svc
from app.services import victims as victims_svc

log = logging.getLogger(__name__)
SEVERITY = {"unclassified": -1, "safe": 0, "caution": 1, "unsafe": 2, "blocked": 3}
MAX_TIMELINE = 250


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def compile_stats(db: AsyncSession, inc: Incident) -> dict[str, Any]:
    users = {u.id: u for u in (await db.execute(select(User))).scalars().unique()}
    name = lambda uid: users[uid].full_name if uid in users else None  # noqa: E731

    floors = (await db.execute(select(Floor).where(Floor.incident_id == inc.id))).scalars().all()
    zones = list(
        (
            await db.execute(
                select(Zone)
                .where(Zone.incident_id == inc.id)
                .order_by(Zone.grid_row, Zone.grid_col)
            )
        ).scalars()
    )
    zone_code = {z.id: z.code for z in zones}
    floor_num = {f.id: f.number for f in floors}

    assessments = list(
        (
            await db.execute(
                select(ZoneAssessment)
                .join(Zone, Zone.id == ZoneAssessment.zone_id)
                .where(Zone.incident_id == inc.id)
                .order_by(ZoneAssessment.created_at)
            )
        ).scalars()
    )
    by_zone: dict[uuid.UUID, list[ZoneAssessment]] = defaultdict(list)
    for a in assessments:
        by_zone[a.zone_id].append(a)

    timeline: list[dict[str, Any]] = [
        {"at": _iso(inc.opened_at), "key": "opened", "params": {"by": inc.reported_by or ""}}
    ]
    zone_rows = []
    for z in zones:
        transitions, prev = [], None
        for a in by_zone[z.id]:
            if not a.analysable or a.status == prev:
                continue
            transitions.append({"at": _iso(a.created_at), "status": a.status})
            if prev is not None:
                timeline.append(
                    {"at": _iso(a.created_at), "key": "zone_change",
                     "params": {"zone": z.code, "from": prev, "to": a.status}}
                )  # fmt: skip
            prev = a.status
        analysable = [a for a in by_zone[z.id] if a.analysable]
        peak = max((a.status for a in analysable), key=SEVERITY.__getitem__, default="unclassified")
        zone_rows.append(
            {
                "code": z.code,
                "label": z.label,
                "floor": floor_num.get(z.floor_id),
                "final_status": z.current_status,
                "final_at": _iso(z.status_updated_at),
                "peak_status": peak,
                "assessments": len(by_zone[z.id]),
                "unanalysable": len(by_zone[z.id]) - len(analysable),
                "transitions": transitions,
            }
        )

    assignments = list(
        (
            await db.execute(
                select(TeamAssignment)
                .where(TeamAssignment.incident_id == inc.id)
                .order_by(TeamAssignment.assigned_at)
            )
        ).scalars()
    )
    team = []
    for a in assignments:
        team.append(
            {
                "responder": name(a.user_id),
                "zone": zone_code.get(a.zone_id),
                "device": a.device_label,
                "assigned_at": _iso(a.assigned_at),
                "unassigned_at": _iso(a.unassigned_at),
            }
        )
        timeline.append(
            {"at": _iso(a.assigned_at), "key": "assigned",
             "params": {"responder": name(a.user_id) or "", "zone": zone_code.get(a.zone_id) or "—"}}
        )  # fmt: skip
    if inc.activated_at:
        timeline.append({"at": _iso(inc.activated_at), "key": "activated", "params": {}})

    alerts = list(
        (
            await db.execute(
                select(Alert).where(Alert.incident_id == inc.id).order_by(Alert.created_at)
            )
        ).scalars()
    )
    alert_rows = [
        {
            "severity": a.severity,
            "type": a.type,
            "message_key": a.message_key,
            "params": a.message_params,
            "at": _iso(a.created_at),
            "acknowledged_by": name(a.acknowledged_by),
        }
        for a in alerts
    ]
    for a in alerts:
        if a.severity in ("crit", "warn"):
            timeline.append(
                {"at": _iso(a.created_at), "key": "alert",
                 "params": {"severity": a.severity, "message_key": a.message_key,
                            "message_params": a.message_params}}
            )  # fmt: skip

    victims = await victims_svc.ranked(db, inc.id)
    victim_rows, rank = [], 0
    for v in victims:
        if v.status == "detected":
            rank += 1
        victim_rows.append(
            {
                "rank": rank if v.status == "detected" else None,
                "posture": v.posture,
                "low_confidence": v.low_confidence,
                "band": v.rpi_band,
                "score": v.rpi_score,
                "zone": v.zone_code,
                "source": v.source,
                "status": v.status,
                "confidence": v.detection_confidence,
                "first_seen_at": _iso(v.first_seen_at),
                "best_detection_id": str(v.best_detection_id) if v.best_detection_id else None,
            }
        )
        if v.rpi_band in ("critical", "high"):
            timeline.append(
                {"at": _iso(v.first_seen_at), "key": "victim",
                 "params": {"band": v.rpi_band, "zone": v.zone_code or "—", "posture": v.posture}}
            )  # fmt: skip

    sessions = (
        (await db.execute(select(CaptureSession).where(CaptureSession.incident_id == inc.id)))
        .scalars()
        .all()
    )
    for s in sessions:
        timeline.append(
            {"at": _iso(s.started_at), "key": "capture",
             "params": {"zone": zone_code.get(s.zone_id) or "", "responder": name(s.user_id) or ""}}
        )  # fmt: skip
    uploads = (
        (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.incident_id == inc.id,
                    MediaAsset.kind.in_(("thermal_image", "thermal_video")),
                )
            )
        )
        .scalars()
        .all()
    )
    for u in uploads:
        timeline.append(
            {"at": _iso(u.created_at), "key": "thermal_upload",
             "params": {"source": u.source, "zone": zone_code.get(u.zone_id) or "—"}}
        )  # fmt: skip
    if inc.closed_at:
        timeline.append(
            {
                "at": _iso(inc.closed_at),
                "key": "closed",
                "params": {"by": name(inc.closed_by) or ""},
            }
        )
    timeline.sort(key=lambda e: e["at"] or "")
    truncated = max(0, len(timeline) - MAX_TIMELINE)
    timeline = timeline[:MAX_TIMELINE]

    # Representative frames: latest RGB frame of the most severe zones, best thermal frames.
    frames = []
    worst = sorted(zone_rows, key=lambda r: SEVERITY[r["peak_status"]], reverse=True)
    for r in worst[:4]:
        z = next(z for z in zones if z.code == r["code"])
        latest = next(
            (a for a in reversed(by_zone[z.id]) if a.media_id is not None and a.analysable), None
        )
        if latest:
            frames.append(
                {"kind": "rgb", "media_id": str(latest.media_id), "zone": z.code,
                 "status": latest.status, "at": _iso(latest.created_at)}
            )  # fmt: skip
    for v in victims[:3]:
        if v.media_id and v.status != "false_positive":
            det = await db.get(ThermalDetection, v.best_detection_id)
            frames.append(
                {"kind": "thermal", "media_id": str(v.media_id),
                 "frame_index": det.frame_index if det else None, "zone": v.zone_code,
                 "band": v.rpi_band, "posture": v.posture, "at": _iso(v.first_seen_at)}
            )  # fmt: skip

    versions: set[str] = set()
    for a in assessments:
        versions.update(f"{k} {val}" for k, val in (a.model_versions or {}).items())
    det_versions = (
        (
            await db.execute(
                select(ThermalDetection.model_versions).where(
                    ThermalDetection.incident_id == inc.id
                )
            )
        )
        .scalars()
        .all()
    )
    for mv in det_versions:
        versions.update(f"{k} {val}" for k, val in (mv or {}).items())
    jobs = (
        await db.execute(
            select(AnalysisJob.model_name, AnalysisJob.model_version)
            .join(MediaAsset, MediaAsset.id == AnalysisJob.media_id)
            .where(MediaAsset.incident_id == inc.id, AnalysisJob.model_name.is_not(None))
        )
    ).all()
    versions.update(f"{n} {v}" for n, v in jobs)

    final = Counter(r["final_status"] for r in zone_rows)
    duration = (
        (inc.closed_at - inc.opened_at).total_seconds() if inc.closed_at and inc.opened_at else None
    )
    n_det = (
        await db.execute(select(func.count()).where(ThermalDetection.incident_id == inc.id))
    ).scalar_one()
    return {
        "incident": {
            "code": inc.code,
            "address": inc.address,
            "city": inc.city,
            "structure_type": inc.structure_type,
            "incident_type": inc.incident_type,
            "reported_by": inc.reported_by,
            "source": inc.source,
            "status": inc.status,
            "commander": name(inc.commander_id),
            "closed_by": name(inc.closed_by),
            "opened_at": _iso(inc.opened_at),
            "activated_at": _iso(inc.activated_at),
            "closed_at": _iso(inc.closed_at),
            "summary_text": inc.summary_text,
        },
        "duration_s": duration,
        "counts": {
            "floors": len(floors),
            "zones": len(zones),
            "responders": len({a.user_id for a in assignments}),
            "zones_final": {s: final.get(s, 0) for s in SEVERITY},
            "peak_status": max(
                (r["peak_status"] for r in zone_rows),
                key=SEVERITY.__getitem__,
                default="unclassified",
            ),
            "victims": sum(1 for v in victim_rows if v["status"] != "false_positive"),
            "victims_by_band": dict(
                Counter(v["band"] for v in victim_rows if v["status"] != "false_positive")
            ),
            "rescued": sum(1 for v in victim_rows if v["status"] == "rescued"),
            "false_positives": sum(1 for v in victim_rows if v["status"] == "false_positive"),
            "alerts_by_severity": dict(Counter(a["severity"] for a in alert_rows)),
            "capture_sessions": len(sessions),
            "frames_analysed": sum(s.frames_analysed for s in sessions),
            "thermal_uploads": len(uploads),
            "detections": n_det,
        },
        "zones": zone_rows,
        "team": team,
        "victims": victim_rows,
        "alerts": alert_rows,
        "timeline": timeline,
        "timeline_truncated": truncated,
        "frames": frames,
        "model_versions": sorted(versions),
        "settings": {
            "stale_zone_seconds": (await settings_svc.load_all(db))["stale_zone_seconds"],
        },
    }


# ---------------------------------------------------------------- narrative

_STATUS_UR = {"safe": "محفوظ", "caution": "احتیاط", "unsafe": "غیر محفوظ", "blocked": "بند",
              "unclassified": "غیر درجہ بند"}  # fmt: skip


def _duration(seconds: float | None, lang: str) -> str:
    if not seconds:
        return "—"
    h, m = int(seconds // 3600), int(seconds % 3600 // 60)
    if lang == "ur":
        return f"{h} گھنٹے {m} منٹ" if h else f"{m} منٹ"
    return f"{h} h {m} min" if h else f"{m} min"


def _local(iso: str | None) -> str:
    """Station-local time for narratives, matching the PDF tables (REPORT_TIMEZONE)."""
    if not iso:
        return "—"
    try:
        tz = ZoneInfo(get_settings().report_timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.fromisoformat(iso).astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")


def _n(count: int, one: str, many: str | None = None) -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


def template_narrative(stats: dict[str, Any], lang: str) -> str:
    """Deterministic narrative from the numbers only (the fallback, and the default)."""
    i, c = stats["incident"], stats["counts"]
    zf, bands = c["zones_final"], c["victims_by_band"]
    crit_alerts = c["alerts_by_severity"].get("crit", 0)
    if lang == "ur":
        return (
            f"واقعہ {i['code']} ({i['address'] or '—'}) {_local(i['opened_at'])} کو درج ہوا "
            f"اور {_duration(stats['duration_s'], 'ur')} بعد بند ہوا۔ {c['floors']} منزلوں کے {c['zones']} زونز میں "
            f"{c['responders']} ریسپانڈرز تعینات کیے گئے۔ بندش کے وقت {zf['safe']} زون محفوظ، {zf['caution']} احتیاط، "
            f"{zf['unsafe']} غیر محفوظ اور {zf['blocked']} بند تھے؛ {zf['unclassified']} زونز کا تازہ تجزیہ موجود نہیں تھا۔ "
            f"سب سے زیادہ خطرے کی سطح «{_STATUS_UR[c['peak_status']]}» رہی۔ {c['victims']} افراد کی نشاندہی ہوئی "
            f"({bands.get('critical', 0)} انتہائی اور {bands.get('high', 0)} زیادہ ترجیح)، جن میں سے {c['rescued']} "
            f"کو بچا لیا گیا۔ {crit_alerts} اہم الرٹس جاری ہوئے۔"
        )
    return (
        f"Incident {i['code']} at {i['address'] or 'an unrecorded address'} was opened at "
        f"{_local(i['opened_at'])} and closed after {_duration(stats['duration_s'], 'en')}. "
        f"{_n(c['responders'], 'responder')} {'was' if c['responders'] == 1 else 'were'} deployed across "
        f"{_n(c['zones'], 'zone')} on {_n(c['floors'], 'floor')}. "
        f"At closure {zf['safe']} zones were safe, {zf['caution']} caution, {zf['unsafe']} unsafe and "
        f"{zf['blocked']} blocked; {zf['unclassified']} had no current analysis. The highest zone risk "
        f"reached was {c['peak_status']}. {_n(c['victims'], 'person', 'people')} "
        f"{'was' if c['victims'] == 1 else 'were'} detected "
        f"({bands.get('critical', 0)} critical and {bands.get('high', 0)} high priority), of whom "
        f"{c['rescued']} {'was' if c['rescued'] == 1 else 'were'} marked rescued. "
        f"{_n(crit_alerts, 'critical alert')} {'was' if crit_alerts == 1 else 'were'} raised."
    )


NARRATIVE_SYSTEM = (
    "You write the narrative paragraph of a fire-incident report for Rescue 1122 (Punjab "
    "Emergency Service). Use ONLY the facts and numbers in the JSON the user provides; never "
    "invent names, causes, times, injuries or numbers that are not in it. If something is "
    "unknown, leave it out. Write one paragraph of 120–200 words of plain prose (no headings, "
    "lists or markdown) in {language}, in a factual operational tone for commanders and "
    "auditors. Mention timing, deployment, how zone risk evolved, people detected by priority, "
    "rescues and critical alerts. Do not add safety advice or disclaimers; the report adds its "
    "own."
)


def _facts(stats: dict[str, Any]) -> str:
    keep = {k: stats[k] for k in ("incident", "duration_s", "counts", "model_versions")}
    keep["zones"] = [
        {k: z[k] for k in ("code", "label", "final_status", "peak_status", "transitions")}
        for z in stats["zones"]
    ]
    keep["timeline"] = stats["timeline"][:80]
    return json.dumps(keep, ensure_ascii=False, default=str)


async def llm_narrative(stats: dict[str, Any], lang: str) -> str:
    language = "Urdu (اردو)" if lang == "ur" else "English"
    return await get_llm().complete(
        NARRATIVE_SYSTEM.format(language=language),
        [{"role": "user", "content": f"Incident report facts (JSON):\n{_facts(stats)}"}],
        max_tokens=1500,
        lang=lang,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------- persistence


async def compile_and_store(
    db: AsyncSession, inc: Incident, user_id: uuid.UUID | None
) -> IncidentReport:
    stats = await compile_stats(db, inc)
    stats["narrative"] = {
        "en": template_narrative(stats, "en"),
        "ur": template_narrative(stats, "ur"),
        "source": "template",
    }
    stats["pdfs"] = {}
    report = (
        await db.execute(select(IncidentReport).where(IncidentReport.incident_id == inc.id))
    ).scalar_one_or_none()
    if report is None:
        report = IncidentReport(incident_id=inc.id)
        db.add(report)
    report.generated_at = datetime.now(UTC)
    report.generated_by = user_id
    report.narrative = stats["narrative"]["en"]
    report.stats = stats
    report.pdf_media_id = None
    await db.flush()
    return report


async def enrich_with_llm(report_id: uuid.UUID) -> None:
    """Background: replace the template narrative with an LLM one when the feature is on.
    Any failure keeps the template (HANDOFF §10)."""
    async with SessionLocal() as db:
        flags = (await settings_svc.load_all(db))["llm.features"]
        report = await db.get(IncidentReport, report_id)
        if not report or not flags.get("report_narrative") or get_llm().name == "template":
            return
        stats = dict(report.stats)
        try:
            en, ur = await asyncio.gather(llm_narrative(stats, "en"), llm_narrative(stats, "ur"))
        except LLMUnavailable as e:
            log.info("report narrative: template kept (%s)", e)
            return
        stats["narrative"] = {"en": en, "ur": ur, "source": "llm"}
        stats["pdfs"] = {}  # PDFs regenerate with the new text
        report.stats = stats
        report.narrative = en
        report.pdf_media_id = None
        await db.commit()


_background: set[asyncio.Task] = set()


def schedule_enrichment(report_id: uuid.UUID) -> None:
    task = asyncio.get_running_loop().create_task(enrich_with_llm(report_id))
    _background.add(task)
    task.add_done_callback(_background.discard)
