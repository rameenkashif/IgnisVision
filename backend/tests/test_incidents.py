from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.engine import SessionLocal
from app.models import AuditLog, TeamAssignment, Zone, ZoneAssessment


async def _set_zone(zone_id, status, *, age_s=0, confidence=0.8):
    """Simulate a zone analysis (the real pipeline arrives in Phase 4)."""
    async with SessionLocal() as db:
        a = ZoneAssessment(
            zone_id=zone_id,
            status=status,
            risk_score=0.5,
            confidence=confidence,
            analysable=True,
            reasons=[],
        )
        db.add(a)
        await db.flush()
        await db.execute(
            update(Zone)
            .where(Zone.id == zone_id)
            .values(
                current_status=status,
                current_assessment_id=a.id,
                status_updated_at=datetime.now(UTC) - timedelta(seconds=age_s),
            )
        )
        await db.commit()


async def test_dispatch_creates_everything_in_one_go(as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    r1, r2 = await make_user("field_responder"), await make_user("field_responder")
    inc = await create_incident(h, [r1, r2])
    assert inc["code"].startswith(f"IV-{datetime.now(UTC).year}-")
    assert inc["status"] == "dispatched"
    assert [f["number"] for f in inc["floors"]] == [1, 2]
    assert len(inc["zones"]) == 8
    assert inc["zones"][0]["code"] == "F1-Z1" and inc["zones"][0]["label"] == "Lobby"
    assert {z["status"] for z in inc["zones"]} == {"unclassified"}
    assert [a["zone_code"] for a in inc["assignments"]] == ["F1-Z1", "F1-Z2"]
    assert inc["zones"][1]["assignees"][0]["id"] == str(r2.id)
    k = inc["kpis"]
    assert k["response_units"] == 2 and k["zones_total"] == 8 and k["classified"] == 0
    assert k["building_status"] == "unclassified" and k["evac_ok_pct"] is None


async def test_codes_are_sequential(as_role, create_incident):
    _, h = await as_role("incident_commander")
    a, b = await create_incident(h), await create_incident(h)
    assert int(b["code"][-4:]) == int(a["code"][-4:]) + 1


async def test_dispatch_rejects_bad_input(client, as_role, make_user):
    _, h = await as_role("incident_commander")
    trainee = await make_user("trainee")
    base = {"address": "X", "floors": 1, "zones_per_floor": 2}
    r = await client.post(
        "/api/v1/incidents", json={**base, "zone_labels": {"F9-Z9": "nope"}}, headers=h
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/incidents",
        json={**base, "assignments": [{"user_id": str(trainee.id), "zone_code": "F1-Z1"}]},
        headers=h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "assignee_not_responder"


async def test_stale_or_unanalysed_zone_is_never_safe(client, as_role, create_incident):
    """HANDOFF §12: an unanalysed or stale zone is never displayed as safe."""
    _, h = await as_role("incident_commander")
    inc = await create_incident(h)
    z1, z2, z3 = (z["id"] for z in inc["zones"][:3])
    await _set_zone(z1, "safe", age_s=10)
    await _set_zone(z2, "safe", age_s=121)  # older than stale_zone_seconds (120)
    await _set_zone(z3, "unsafe", age_s=5)
    d = (await client.get(f"/api/v1/incidents/{inc['id']}", headers=h)).json()
    zones = {z["id"]: z for z in d["zones"]}
    assert zones[z1]["status"] == "safe" and not zones[z1]["stale"]
    assert zones[z2]["status"] == "unclassified" and zones[z2]["stale"]
    assert zones[z2]["stored_status"] == "safe"
    assert zones[z3]["status"] == "unsafe"
    k = d["kpis"]
    assert k["zones_by_status"]["safe"] == 1 and k["zones_by_status"]["unclassified"] == 6
    assert k["classified"] == 2 and k["building_status"] == "unsafe"
    assert k["evac_ok_pct"] == 50.0 and k["unclassified_pct"] == 75.0
    assert k["below_threshold"] is False  # 50% ≥ 40% threshold
    assert k["ai_confidence"] == 0.8


async def test_evacuation_threshold_from_settings(client, as_role, create_incident):
    _, h_admin = await as_role("admin")
    await client.patch(
        "/api/v1/admin/settings", json={"evacuation_threshold_pct": 60}, headers=h_admin
    )
    _, h = await as_role("incident_commander")
    inc = await create_incident(h)
    await _set_zone(inc["zones"][0]["id"], "safe")
    await _set_zone(inc["zones"][1]["id"], "blocked")
    k = (await client.get(f"/api/v1/incidents/{inc['id']}", headers=h)).json()["kpis"]
    assert k["evacuation_threshold_pct"] == 60 and k["below_threshold"] is True
    assert k["building_status"] == "blocked"


async def test_lifecycle_dispatched_active_closed(client, as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    r1 = await make_user("field_responder")
    inc = await create_incident(h, [r1])
    url = f"/api/v1/incidents/{inc['id']}"
    r = await client.post(f"{url}/activate", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["activated_at"]
    assert (await client.post(f"{url}/activate", headers=h)).status_code == 409
    r = await client.post(f"{url}/close", json={"confirm": False}, headers=h)
    assert r.status_code == 400
    r = await client.post(f"{url}/close", json={"confirm": True}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert r.json()["assignments"] == []  # active assignments ended, history kept
    hist = await client.get(f"{url}/assignments", params={"include_history": True}, headers=h)
    assert hist.json()[0]["unassigned_at"] is not None
    r = await client.patch(url, json={"address": "Elsewhere"}, headers=h)
    assert r.status_code == 409
    r = await client.patch(url, json={"summary_text": "Post-incident notes"}, headers=h)
    assert r.status_code == 200


async def test_reassignment_keeps_history(client, as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    r1 = await make_user("field_responder")
    inc = await create_incident(h, [r1])
    z4 = next(z for z in inc["zones"] if z["code"] == "F1-Z4")
    r = await client.post(
        f"/api/v1/incidents/{inc['id']}/assignments",
        json={"user_id": str(r1.id), "zone_id": z4["id"], "device_label": "Rig 9"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["zone_code"] == "F1-Z4"
    async with SessionLocal() as db:
        rows = (
            (await db.execute(select(TeamAssignment).where(TeamAssignment.user_id == r1.id)))
            .scalars()
            .all()
        )
    assert len(rows) == 2 and sum(a.unassigned_at is None for a in rows) == 1
    d = (await client.get(f"/api/v1/incidents/{inc['id']}", headers=h)).json()
    assert [a["zone_code"] for a in d["assignments"]] == ["F1-Z4"]

    r = await client.delete(f"/api/v1/assignments/{r.json()['id']}", headers=h)
    assert r.status_code == 200 and r.json()["unassigned_at"]
    d = (await client.get(f"/api/v1/incidents/{inc['id']}", headers=h)).json()
    assert d["assignments"] == [] and d["kpis"]["response_units"] == 0


async def test_assignment_validation(client, as_role, make_user, create_incident):
    _, h = await as_role("incident_commander")
    inc, other = await create_incident(h), await create_incident(h)
    r1 = await make_user("field_responder")
    r = await client.post(
        f"/api/v1/incidents/{inc['id']}/assignments",
        json={"user_id": str(r1.id), "zone_id": other["zones"][0]["id"]},
        headers=h,
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "zone_not_in_incident"


async def test_my_assignments_and_responders(client, as_role, make_user, login, create_incident):
    _, h = await as_role("incident_commander")
    r1 = await make_user("field_responder", full_name="Ali Raza")
    await make_user("field_responder", full_name="Bilal Khan")
    inc = await create_incident(h, [r1])
    rs = (await client.get("/api/v1/responders", headers=h)).json()
    assert [(r["full_name"], r["active_incident_code"]) for r in rs] == [
        ("Ali Raza", inc["code"]),
        ("Bilal Khan", None),
    ]
    h_r1 = await login(r1)
    mine = (await client.get("/api/v1/assignments/mine", headers=h_r1)).json()
    assert [(m["incident_code"], m["zone_code"]) for m in mine] == [(inc["code"], "F1-Z1")]


async def test_zone_label_and_history(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    inc = await create_incident(h)
    zid = inc["zones"][2]["id"]
    r = await client.patch(f"/api/v1/zones/{zid}", json={"label": "Stairwell"}, headers=h)
    assert r.status_code == 200 and r.json()["label"] == "Stairwell"
    await _set_zone(zid, "caution")
    await _set_zone(zid, "unsafe")
    hist = (await client.get(f"/api/v1/zones/{zid}/assessments", headers=h)).json()
    assert [a["status"] for a in hist] == ["unsafe", "caution"]


async def test_list_filters(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    a = await create_incident(h, address="Anarkali Bazaar")
    await create_incident(h, address="Liberty Market")
    await client.post(f"/api/v1/incidents/{a['id']}/activate", headers=h)
    r = await client.get("/api/v1/incidents", params={"status": "active"}, headers=h)
    assert [i["id"] for i in r.json()["items"]] == [a["id"]]
    r = await client.get("/api/v1/incidents", params={"q": "liberty"}, headers=h)
    assert r.json()["total"] == 1


async def test_admin_delete_is_soft_and_audited(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    inc = await create_incident(h)
    admin, h_admin = await as_role("admin")
    url = f"/api/v1/incidents/{inc['id']}"
    r = await client.request("DELETE", url, json={"confirm": False}, headers=h_admin)
    assert r.status_code == 400
    r = await client.request("DELETE", url, json={"confirm": True}, headers=h_admin)
    assert r.status_code == 204
    assert (await client.get(url, headers=h_admin)).status_code == 404
    async with SessionLocal() as db:
        [entry] = (
            (await db.execute(select(AuditLog).where(AuditLog.action == "incident.delete")))
            .scalars()
            .all()
        )
    assert entry.actor_user_id == admin.id and entry.before["code"] == inc["code"]


async def test_alerts_list_and_ack(client, as_role, create_incident):
    from app.services.alerts import create_alert

    commander, h = await as_role("incident_commander")
    inc = await create_incident(h)
    async with SessionLocal() as db:
        await create_alert(
            db,
            incident_id=inc["id"],
            severity="crit",
            type="zone_unsafe",
            message_key="alerts.zone_unsafe",
            params={"zone": "F1-Z2"},
        )
    r = await client.get(f"/api/v1/incidents/{inc['id']}/alerts", headers=h)
    [alert] = r.json()["items"]
    assert alert["message_params"] == {"zone": "F1-Z2"} and alert["acknowledged_at"] is None
    r = await client.post(f"/api/v1/alerts/{alert['id']}/ack", headers=h)
    assert r.json()["acknowledged_by"] == str(commander.id)
    r = await client.get(
        f"/api/v1/incidents/{inc['id']}/alerts", params={"unacknowledged": True}, headers=h
    )
    assert r.json()["total"] == 0
