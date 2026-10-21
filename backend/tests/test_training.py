import json
import uuid

import pytest
from sqlalchemy import select

from app.db.engine import SessionLocal
from app.db.placeholders import seed_placeholder_scenarios, zone_image
from app.llm.base import LLMUnavailable
from app.llm.registry import set_llm
from app.models import ScenarioItem, TrainingAttempt, TrainingScenario
from app.services import training as svc
from tests.test_thermal import mp4


async def _seed() -> list[TrainingScenario]:
    async with SessionLocal() as db:
        await seed_placeholder_scenarios(db)
        await db.commit()
        return list((await db.execute(select(TrainingScenario))).scalars())


def _item(gt: dict, ref: dict | None = None) -> ScenarioItem:
    return ScenarioItem(ground_truth=gt, reference_output=ref, order=0)


ZONE_GT = {
    "type": "zone",
    "regions": [
        {"id": "r1", "polygon": [[0, 0], [1, 0], [1, 1]], "status": "unsafe"},
        {"id": "r2", "polygon": [[0, 0], [1, 0], [1, 1]], "status": "safe"},
    ],
}
ZONE_REF = {"type": "zone", "regions": {"r1": {"status": "caution"}, "r2": {"status": None}}}


def test_grading_exact_and_model_agreement():
    res = svc.grade_item(
        _item(ZONE_GT, ZONE_REF),
        {"regions": {"r1": "caution", "r2": "safe"}},
        {"partial_credit_adjacent": False, "adjacent_credit": 0.5},
    )
    assert [(r["credit"], r["correct"]) for r in res] == [(0.0, False), (1.0, True)]
    assert res[0]["agrees_with_model"] is True  # trainee and model both said caution
    assert res[1]["agrees_with_model"] is None  # model had no analysable answer


def test_grading_partial_credit_adjacent_only_when_enabled():
    grading = {"partial_credit_adjacent": True, "adjacent_credit": 0.5}
    res = svc.grade_item(_item(ZONE_GT), {"regions": {"r1": "caution", "r2": "unsafe"}}, grading)
    assert [r["credit"] for r in res] == [0.5, 0.0]  # caution~unsafe adjacent; safe→unsafe not
    assert not res[0]["correct"]
    missing = svc.grade_item(_item(ZONE_GT), {"regions": {}}, grading)
    assert [r["answer"] for r in missing] == [None, None]
    assert all(r["credit"] == 0 for r in missing)


def test_posture_grading_has_no_partial_credit():
    gt = {"type": "posture", "people": [{"id": "p1", "bbox": [0, 0, 1, 1], "posture": "lying"}]}
    res = svc.grade_item(
        _item(gt), {"people": {"p1": "sitting"}}, {"partial_credit_adjacent": True}
    )
    assert res[0]["credit"] == 0.0


async def test_placeholder_references_follow_the_painted_damage():
    scenarios = await _seed()
    assert len(scenarios) == 3 and all(s.is_placeholder for s in scenarios)
    assert len(await _seed()) == 3  # idempotent
    async with SessionLocal() as db:
        sc = next(s for s in scenarios if s.kind == "zone")
        item = (await svc.items_with_media(db, sc.id))[0][0]
    ref = item.reference_output["regions"]
    truth = {r["id"]: r["status"] for r in item.ground_truth["regions"]}
    assert {k: v["status"] for k, v in ref.items()} == truth
    assert "mock-segformer" in item.reference_model_version
    assert item.ground_truth["explanation_en"].startswith("PLACEHOLDER")


async def test_trainee_flow_hides_then_reveals_ground_truth(client, as_role, make_user, login):
    await _seed()
    trainee, h = await as_role("trainee")
    scs = (await client.get("/api/v1/training/scenarios", headers=h)).json()
    assert len(scs) == 3
    zone = next(s for s in scs if s["kind"] == "zone")
    detail = (await client.get(f"/api/v1/training/scenarios/{zone['id']}", headers=h)).json()
    assert detail["item_count"] == 2
    for it in detail["items"]:
        assert all(set(r) == {"id", "polygon"} for r in it["regions"])
        assert "ground_truth" not in json.dumps(it) and "status" not in json.dumps(it)

    r = await client.post(f"/api/v1/training/scenarios/{zone['id']}/attempts", headers=h)
    assert r.status_code == 201, r.text
    att = r.json()
    assert att["submitted_at"] is None and att["items"][0]["ground_truth"] is None

    async with SessionLocal() as db:  # answer item 1 right, item 2 with one mistake
        items = [i for i, _ in await svc.items_with_media(db, uuid.UUID(zone["id"]))]
    answers = {}
    for n, item in enumerate(items):
        regions = {x["id"]: x["status"] for x in item.ground_truth["regions"]}
        if n == 1:
            regions["r3"] = "caution"  # truth: unsafe
        answers[str(item.id)] = {"regions": regions}
    r = await client.post(
        f"/api/v1/training/attempts/{att['id']}/submit", json={"answers": answers}, headers=h
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["total_targets"] == 7 and res["correct_targets"] == 6
    assert res["score_pct"] == pytest.approx(85.7)
    assert res["model_agreement_pct"] is not None
    wrong = [t for it in res["items"] for t in it["targets"] if not t["correct"]]
    assert wrong == [
        {"id": "r3", "answer": "caution", "truth": "unsafe", "model": "caution", "credit": 0.0,
         "correct": False, "agrees_with_model": True}
    ]  # fmt: skip
    assert res["items"][1]["ground_truth"]["explanation_en"]
    assert res["items"][1]["reference_output"]["type"] == "zone"
    assert res["llm_feedback_pending"] is False

    r = await client.post(
        f"/api/v1/training/attempts/{att['id']}/submit", json={"answers": answers}, headers=h
    )
    assert r.status_code == 409
    # Retry (SRS UC-06 AF): a new attempt
    r2 = await client.post(f"/api/v1/training/scenarios/{zone['id']}/attempts", headers=h)
    assert r2.status_code == 201 and r2.json()["id"] != att["id"]
    scs = (await client.get("/api/v1/training/scenarios", headers=h)).json()
    zone = next(s for s in scs if s["kind"] == "zone")
    assert zone["attempts"] == 1 and zone["best_score"] == pytest.approx(85.7)

    # Visibility: own only for trainees; staff/commanders/admins see everyone's
    other, h2 = await as_role("trainee")
    assert (
        await client.get(f"/api/v1/training/attempts/{att['id']}", headers=h2)
    ).status_code == 404
    assert (await client.get("/api/v1/training/attempts", headers=h2)).json() == []
    r = await client.get(f"/api/v1/training/attempts?user_id={trainee.id}", headers=h2)
    assert r.status_code == 403
    for role in ("training_staff", "incident_commander", "admin"):
        _, hs = await as_role(role)
        rows = (
            await client.get(f"/api/v1/training/attempts?user_id={trainee.id}", headers=hs)
        ).json()
        assert [x["id"] for x in rows] == [att["id"]], role
        full = (await client.get(f"/api/v1/training/attempts/{att['id']}", headers=hs)).json()
        assert full["score_pct"] == pytest.approx(85.7)
    # Admins manage scenarios but don't attempt them (HANDOFF §6)
    _, ha = await as_role("admin")
    assert (await client.get("/api/v1/training/scenarios", headers=ha)).status_code == 403


async def test_trainee_gets_403_on_incidents(client, as_role):
    _, h = await as_role("trainee")
    assert (await client.get("/api/v1/incidents", headers=h)).status_code == 403


async def test_admin_builds_a_scenario(client, as_role):
    _, ha = await as_role("admin")
    _, ht = await as_role("trainee")
    r = await client.post(
        "/api/v1/admin/scenarios",
        json={"title_en": "Stairwell", "title_ur": "سیڑھیاں", "kind": "zone", "difficulty": 2},
        headers=ha,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    png, polys = zone_image(1, 2, [0, 2], seed=7)
    r = await client.post(
        f"/api/v1/admin/scenarios/{sid}/items",
        files={"file": ("a.png", png, "image/png")},
        headers=ha,
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["usable"] is False and item["ground_truth"]["type"] == "zone"
    # unusable → scenario hidden from trainees
    assert (await client.get("/api/v1/training/scenarios", headers=ht)).json() == []

    gt = {"type": "zone", "explanation_en": "Right side spalling.",
          "regions": [{"id": "a", "polygon": polys[0], "status": "safe"},
                      {"id": "b", "polygon": polys[1], "status": "unsafe"}]}  # fmt: skip
    r = await client.patch(
        f"/api/v1/admin/scenarios/{sid}/items/{item['id']}", json={"ground_truth": gt}, headers=ha
    )
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["usable"] is True
    assert item["reference_output"]["regions"]["b"]["status"] == "unsafe"
    bad = dict(gt, regions=[{"id": "a", "polygon": [[0, 0], [2, 0], [1, 1]], "status": "safe"}])
    r = await client.patch(
        f"/api/v1/admin/scenarios/{sid}/items/{item['id']}", json={"ground_truth": bad}, headers=ha
    )
    assert r.status_code == 422
    r = await client.post(
        f"/api/v1/admin/scenarios/{sid}/items",
        files={"file": ("a.png", png, "image/png")},
        data={"ground_truth": "{not json"},
        headers=ha,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_ground_truth"

    # video item labelled on a chosen frame
    vgt = {
        "type": "posture",
        "frame_s": 1.0,
        "people": [{"id": "p1", "bbox": [0.1, 0.4, 0.3, 0.9], "posture": "standing"}],
    }
    r = await client.post(
        f"/api/v1/admin/scenarios/{sid}/items",
        files={"file": ("v.mp4", mp4(), "video/mp4")},
        data={"ground_truth": json.dumps(vgt)},
        headers=ha,
    )
    assert r.status_code == 201, r.text
    assert r.json()["media_kind"] == "video" and r.json()["usable"] is True

    scs = (await client.get("/api/v1/training/scenarios", headers=ht)).json()
    assert [s["title_en"] for s in scs] == ["Stairwell"] and scs[0]["item_count"] == 2
    r = await client.post(f"/api/v1/admin/scenarios/{sid}/recompute-reference", headers=ha)
    assert r.json()["computed"] == 2 and r.json()["failed"] == 0

    await client.patch(f"/api/v1/admin/scenarios/{sid}", json={"is_active": False}, headers=ha)
    assert (await client.get("/api/v1/training/scenarios", headers=ht)).json() == []
    assert (await client.get(f"/api/v1/training/scenarios/{sid}", headers=ht)).status_code == 404
    r = await client.request(
        "DELETE", f"/api/v1/admin/scenarios/{sid}", json={"confirm": False}, headers=ha
    )
    assert r.status_code == 400
    r = await client.request(
        "DELETE", f"/api/v1/admin/scenarios/{sid}", json={"confirm": True}, headers=ha
    )
    assert r.status_code == 204
    assert (await client.get("/api/v1/admin/scenarios", headers=ha)).json() == []


class FakeLLM:
    name = "fake"

    def __init__(self, fail: bool = False):
        self.fail, self.calls = fail, []

    async def complete(self, system, messages, max_tokens, lang):
        self.calls.append((system, messages, lang))
        if self.fail:
            raise LLMUnavailable("down")
        return f"Feedback ({lang})"


async def _wrong_attempt(client, h) -> str:
    scs = (await client.get("/api/v1/training/scenarios", headers=h)).json()
    sid = next(s["id"] for s in scs if s["kind"] == "posture")
    att = (await client.post(f"/api/v1/training/scenarios/{sid}/attempts", headers=h)).json()
    answers = {it["id"]: {"people": {p["id"]: "standing" for p in it["people"]}}
               for it in att["items"]}  # fmt: skip
    r = await client.post(
        f"/api/v1/training/attempts/{att['id']}/submit", json={"answers": answers}, headers=h
    )
    return r.json()


@pytest.mark.parametrize("fail", [False, True])
async def test_llm_feedback_when_enabled(client, as_role, fail):
    await _seed()
    _, ha = await as_role("admin")
    await client.patch(
        "/api/v1/admin/settings",
        json={"llm.features": {"report_narrative": False, "trainer_feedback": True,
                               "help_assistant": False}},
        headers=ha,
    )  # fmt: skip
    fake = FakeLLM(fail)
    set_llm(fake)
    try:
        _, h = await as_role("trainee")
        res = await _wrong_attempt(client, h)
        assert res["llm_feedback_pending"] is True
        await svc.llm_feedback_for(uuid.UUID(res["id"]))
        out = (await client.get(f"/api/v1/training/attempts/{res['id']}", headers=h)).json()
    finally:
        set_llm(None)
    assert out["llm_feedback_pending"] is False
    assert out["llm_feedback"] == (None if fail else "Feedback (en)")
    facts = json.loads(fake.calls[0][1][0]["content"])
    assert facts["items"] and facts["items"][0]["explanation"].startswith("PLACEHOLDER")


async def test_no_llm_call_when_flag_off(client, as_role):
    await _seed()
    fake = FakeLLM()
    set_llm(fake)
    try:
        _, h = await as_role("trainee")
        res = await _wrong_attempt(client, h)
    finally:
        set_llm(None)
    assert res["llm_feedback_pending"] is False and fake.calls == []
    async with SessionLocal() as db:
        att = await db.get(TrainingAttempt, uuid.UUID(res["id"]))
        assert att.feedback["llm"] == "off"
