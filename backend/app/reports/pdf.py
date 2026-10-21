"""PDF rendering with WeasyPrint (Pango/HarfBuzz shaping → correct Urdu Nastaliq, RTL).
Fonts are bundled (SIL OFL) so output is identical in every environment."""

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings
from app.reports.labels import ENUMS, LABELS
from app.services.reports import _duration

HERE = Path(__file__).parent
FONTS = HERE / "fonts"
_env = Environment(
    loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"])
)

STATUS_COLOR = {"safe": "#2FA66E", "caution": "#E8A93B", "unsafe": "#DD4A32",
                "blocked": "#6B2E33", "unclassified": "#B8BEC4"}  # fmt: skip
BAND_COLOR = {"critical": "#D81B44", "high": "#E8622C", "medium": "#C99A14", "low": "#2B8CBE"}


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().report_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _dt(value: str | None, with_date: bool = True) -> str:
    """Local time of the station (REPORT_TIMEZONE), always with the zone abbreviation."""
    if not value:
        return "—"
    d = datetime.fromisoformat(value).astimezone(_tz())
    return d.strftime("%d %b %Y %H:%M %Z" if with_date else "%H:%M:%S")


def _fmt(template: str, params: dict[str, Any]) -> str:
    try:
        return template.format(**{k: ("" if v is None else v) for k, v in params.items()})
    except (KeyError, IndexError):
        return template


def history_svg(stats: dict[str, Any], lang: str) -> str:
    """One bar per zone, coloured by status over the incident's duration."""
    zones = stats["zones"]
    inc = stats["incident"]
    start = datetime.fromisoformat(inc["opened_at"]).astimezone(_tz())
    end = datetime.fromisoformat(inc["closed_at"] or max(
        [t["at"] for z in zones for t in z["transitions"]] or [inc["opened_at"]]
    )).astimezone(_tz())  # fmt: skip
    span = max(1.0, (end - start).total_seconds())
    left, width, row = 70, 420, 16
    height = 24 + row * len(zones)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{left + width + 10}" height="{height}" '
             f'font-family="Noto Sans" font-size="9">']  # fmt: skip
    for i, z in enumerate(zones):
        y = 4 + i * row
        parts.append(f'<text x="0" y="{y + 10}" fill="#333">{z["code"]}</text>')
        parts.append(
            f'<rect x="{left}" y="{y}" width="{width}" height="{row - 4}" fill="#EEF0F2"/>'
        )
        trans = z["transitions"]
        for j, t in enumerate(trans):
            t0 = (datetime.fromisoformat(t["at"]) - start).total_seconds()
            t1 = (
                (datetime.fromisoformat(trans[j + 1]["at"]) - start).total_seconds()
                if j + 1 < len(trans)
                else span
            )
            x0 = left + width * max(0.0, t0) / span
            x1 = left + width * min(span, t1) / span
            parts.append(
                f'<rect x="{x0:.1f}" y="{y}" width="{max(1.0, x1 - x0):.1f}" height="{row - 4}" '
                f'fill="{STATUS_COLOR[t["status"]]}"/>'
            )
    axis_y = height - 6
    parts.append(f'<text x="{left}" y="{axis_y}" fill="#666">{start:%H:%M}</text>')
    parts.append(
        f'<text x="{left + width}" y="{axis_y}" fill="#666" text-anchor="end">{end:%H:%M}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def render_pdf(
    stats: dict[str, Any], lang: str, frame_paths: list[tuple[dict, str]], generated_at: datetime
) -> bytes:
    from weasyprint import HTML  # heavy import, only when rendering

    L, E = LABELS[lang], ENUMS[lang]

    def event_text(e: dict) -> str:
        p = dict(e["params"])
        for k in ("from", "to"):
            if k in p:
                p[k] = E["status"].get(p[k], p[k])
        if "band" in p:
            p["band"] = E["band"].get(p["band"], p["band"])
        if "posture" in p:
            p["posture"] = E["posture"].get(p["posture"], p["posture"])
        if "source" in p:
            p["source"] = E["source"].get(p["source"], p["source"])
        if e["key"] == "alert":
            p["message"] = alert_text(p.get("message_key", ""), p.get("message_params", {}))
        return _fmt(E["event"].get(e["key"], e["key"]), p)

    def alert_text(key: str, params: dict) -> str:
        p = dict(params)
        for k in ("from", "to"):
            if k in p:
                p[k] = E["status"].get(p[k], p[k])
        return _fmt(E["alert"].get(key, key), p)

    html = _env.get_template("report.html").render(
        s=stats, L=L, E=E, lang=lang, dir="rtl" if lang == "ur" else "ltr",
        fonts=FONTS.as_uri(), dt=_dt, event_text=event_text, alert_text=alert_text,
        history_svg=history_svg(stats, lang), status_color=STATUS_COLOR, band_color=BAND_COLOR,
        frames=frame_paths, generated_at=generated_at.astimezone(_tz()).strftime("%d %b %Y %H:%M %Z"),
        duration=_duration(stats.get("duration_s"), lang),
    )  # fmt: skip
    return HTML(string=html, base_url=str(HERE)).write_pdf()
