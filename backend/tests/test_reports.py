from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update

from app.db.engine import SessionLocal
from app.llm.base import LLMUnavailable
from app.llm.registry import set_llm
from app.models import IncidentReport, Zone, ZoneAssessment
from app.services import reports as reports_svc


async def _closed_incident(client, h, create_incident, make_user):
    r1 = await make_user("field_responder", full_name="Ali Raza")
    inc = await create_incident(h, [r1])
    zid = inc["zones"][1]["id"]
    async with SessionLocal() as db:  # some zone history
        for status in ("safe", "caution", "unsafe"):
            a = ZoneAssessment(
                zone_id=zid,
                status=status,
                risk_score=0.5,
                confidence=0.8,
                analysable=True,
                reasons=[],
                model_versions={"seg": "v1"},
            )
            db.add(a)
            await db.flush()
        await db.execute(
            update(Zone).where(Zone.id == zid).values(
                current_status="unsafe", current_assessment_id=a.id,
                status_updated_at=datetime.now(UTC))
        )  # fmt: skip
        await db.commit()
    await client.post(f"/api/v1/incidents/{inc['id']}/activate", headers=h)
    r = await client.post(f"/api/v1/incidents/{inc['id']}/close", json={"confirm": True}, headers=h)
    assert r.status_code == 200
    return inc


async def test_close_compiles_report(client, as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    inc = await _closed_incident(client, h, create_incident, make_user)
    r = await client.get(f"/api/v1/incidents/{inc['id']}/report", headers=h)
    assert r.status_code == 200, r.text
    rep = r.json()
    s = rep["stats"]
    assert rep["narrative_source"] == "template"
    assert inc["code"] in rep["narrative_en"] and inc["code"] in rep["narrative_ur"]
    assert s["counts"]["zones"] == 8 and s["counts"]["responders"] == 1
    z2 = next(z for z in s["zones"] if z["code"] == "F1-Z2")
    assert z2["final_status"] == "unsafe" and z2["peak_status"] == "unsafe"
    assert [t["status"] for t in z2["transitions"]] == ["safe", "caution", "unsafe"]
    keys = [e["key"] for e in s["timeline"]]
    assert keys[0] == "opened" and keys[-1] == "closed" and "zone_change" in keys
    assert s["team"][0]["responder"] == "Ali Raza" and s["team"][0]["unassigned_at"]
    assert "seg v1" in s["model_versions"]


async def test_report_requires_closed_incident(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    inc = await create_incident(h)
    r = await client.get(f"/api/v1/incidents/{inc['id']}/report", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "incident_not_closed"


@pytest.mark.parametrize("lang", ["en", "ur"])
async def test_pdf_in_both_languages_is_cached(client, as_role, make_user, create_incident, lang):
    _, h = await as_role("incident_commander")
    inc = await _closed_incident(client, h, create_incident, make_user)
    url = f"/api/v1/incidents/{inc['id']}/report.pdf?lang={lang}"
    r = await client.get(url, headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-" and len(r.content) > 10_000
    assert f'{inc["code"]}-report-{lang}.pdf' in r.headers["content-disposition"]
    async with SessionLocal() as db:
        rep = (await db.execute(select(IncidentReport))).scalar_one()
        assert lang in rep.stats["pdfs"]
    again = await client.get(url, headers=h)
    assert again.content == r.content  # served from the cache


async def test_regenerate_resets_pdfs(client, as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    inc = await _closed_incident(client, h, create_incident, make_user)
    await client.get(f"/api/v1/incidents/{inc['id']}/report.pdf", headers=h)
    r = await client.post(f"/api/v1/incidents/{inc['id']}/report/regenerate", headers=h)
    assert r.status_code == 200
    async with SessionLocal() as db:
        rep = (await db.execute(select(IncidentReport))).scalar_one()
        assert rep.stats["pdfs"] == {}


class FakeLLM:
    name = "fake"

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    async def complete(self, system, messages, max_tokens, lang):
        self.calls.append((system, messages, lang))
        if self.fail:
            raise LLMUnavailable("refusal")
        return f"LLM narrative ({lang})"


async def _enable_llm_flag(client, as_role):
    _, ha = await as_role("admin")
    await client.patch(
        "/api/v1/admin/settings",
        json={
            "llm.features": {
                "report_narrative": True,
                "trainer_feedback": False,
                "help_assistant": False,
            }
        },
        headers=ha,
    )


async def test_llm_narrative_replaces_template_when_enabled(
    client, as_role, make_user, create_incident
):
    _, h = await as_role("incident_commander")
    inc = await _closed_incident(client, h, create_incident, make_user)
    await _enable_llm_flag(client, as_role)
    fake = FakeLLM()
    set_llm(fake)
    try:
        async with SessionLocal() as db:
            rep = (await db.execute(select(IncidentReport))).scalar_one()
        await reports_svc.enrich_with_llm(rep.id)
    finally:
        set_llm(None)
    r = (await client.get(f"/api/v1/incidents/{inc['id']}/report", headers=h)).json()
    assert r["narrative_source"] == "llm"
    assert r["narrative_en"] == "LLM narrative (en)" and r["narrative_ur"] == "LLM narrative (ur)"
    system, messages, _ = fake.calls[0]
    assert "ONLY the facts" in system and inc["code"] in messages[0]["content"]


async def test_llm_failure_keeps_template(client, as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    inc = await _closed_incident(client, h, create_incident, make_user)
    await _enable_llm_flag(client, as_role)
    set_llm(FakeLLM(fail=True))
    try:
        async with SessionLocal() as db:
            rep = (await db.execute(select(IncidentReport))).scalar_one()
        await reports_svc.enrich_with_llm(rep.id)
    finally:
        set_llm(None)
    r = (await client.get(f"/api/v1/incidents/{inc['id']}/report", headers=h)).json()
    assert r["narrative_source"] == "template"


async def test_llm_not_called_when_flag_off(client, as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    await _closed_incident(client, h, create_incident, make_user)
    fake = FakeLLM()
    set_llm(fake)
    try:
        async with SessionLocal() as db:
            rep = (await db.execute(select(IncidentReport))).scalar_one()
        await reports_svc.enrich_with_llm(rep.id)
    finally:
        set_llm(None)
    assert fake.calls == []


async def test_anthropic_provider_maps_refusal_to_fallback(monkeypatch):
    from types import SimpleNamespace

    from app.llm.anthropic_provider import AnthropicProvider

    p = AnthropicProvider("test-key", "claude-opus-5-5")
    captured = {}

    async def fake_create(**kw):
        captured.update(kw)
        return SimpleNamespace(
            stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"), content=[]
        )

    monkeypatch.setattr(p._client.beta.messages, "create", fake_create)
    with pytest.raises(LLMUnavailable):
        await p.complete("sys", [{"role": "user", "content": "x"}], 100, "en")
    assert captured["model"] == "claude-opus-5-5" and captured["fallbacks"] == "default"

    async def ok_create(**kw):
        return SimpleNamespace(
            stop_reason="end_turn",
            stop_details=None,
            content=[SimpleNamespace(type="text", text=" Narrative. ")],
        )

    monkeypatch.setattr(p._client.beta.messages, "create", ok_create)
    assert await p.complete("sys", [], 100, "en") == "Narrative."


async def test_seed_demo_incident_is_idempotent():
    from app.db.seed import seed

    first = await seed()
    second = await seed()
    assert first["demo_incident"].endswith("(created)")
    assert second["demo_incident"].endswith("(already present)")
    async with SessionLocal() as db:
        rep = (await db.execute(select(IncidentReport))).scalar_one()
    assert rep.stats["counts"]["victims"] == 4 and rep.stats["counts"]["peak_status"] == "blocked"
