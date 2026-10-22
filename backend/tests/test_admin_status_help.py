from datetime import UTC, datetime, timedelta

import pytest

from app.api.v1 import help as help_api
from app.llm.base import LLMUnavailable
from app.llm.registry import set_llm


async def test_status_reports_components(client, as_role, tmp_path, monkeypatch):
    _, h = await as_role("admin")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    (tmp_path / "ignis-20261020T000000Z.dump").write_bytes(b"x" * 10)
    (tmp_path / "LAST_BACKUP").write_text(datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    r = await client.get("/api/v1/admin/status", headers=h)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["database"]["ok"] and s["database"]["migration"]
    assert s["ml"]["backend"] == "mock" and s["ml"]["models"]
    assert s["backups"]["count"] == 1 and s["backups"]["stale"] is False
    assert s["users"]["active_by_role"]["admin"] >= 1 and s["users"]["active_sessions"] >= 1
    assert set(s["jobs"]["by_status"]) == {"queued", "running", "done", "failed"}
    assert "backup_stale" not in s["warnings"]

    old = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "LAST_BACKUP").write_text(old)
    s = (await client.get("/api/v1/admin/status", headers=h)).json()
    assert s["status"] == "warn" and "backup_stale" in s["warnings"]

    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "missing"))
    s = (await client.get("/api/v1/admin/status", headers=h)).json()
    assert s["backups"] == {"available": False} and "backups_not_visible" in s["warnings"]


async def test_audit_filters_names_and_facets(client, as_role, make_user):
    admin, h = await as_role("admin")
    target = await make_user("trainee")
    r = await client.post(
        f"/api/v1/users/{target.id}/deactivate", json={"confirm": True}, headers=h
    )
    assert r.status_code == 200
    rows = (await client.get("/api/v1/admin/audit-logs?action=user.deactivate", headers=h)).json()
    assert rows["total"] == 1
    item = rows["items"][0]
    assert item["actor_username"] == admin.username and item["actor_name"] == admin.full_name
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    r = await client.get("/api/v1/admin/audit-logs", params={"from": future}, headers=h)
    assert r.json()["total"] == 0
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    r = await client.get("/api/v1/admin/audit-logs", params={"from": past, "to": future}, headers=h)
    assert r.json()["total"] >= 1
    facets = (await client.get("/api/v1/admin/audit-logs/facets", headers=h)).json()
    assert "user.deactivate" in facets["actions"] and "user" in facets["entity_types"]


async def test_users_list_shows_last_login(client, as_role):
    admin, h = await as_role("admin")
    users = (await client.get("/api/v1/users", headers=h)).json()["items"]
    me = next(u for u in users if u["id"] == str(admin.id))
    assert me["last_login_at"] is not None


class FakeLLM:
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    async def complete(self, system, messages, max_tokens, lang):
        self.calls.append((system, messages, lang))
        if self.fail:
            raise LLMUnavailable("down")
        return "Open Live monitoring and press +."


async def _flag(client, as_role, on: bool):
    _, ha = await as_role("admin")
    await client.patch(
        "/api/v1/admin/settings",
        json={"llm.features": {"report_narrative": False, "trainer_feedback": False,
                               "help_assistant": on}},
        headers=ha,
    )  # fmt: skip


BODY = {"question": "How do I log an emergency?", "topic": "live",
        "context": "To log an emergency press the + button.", "lang": "ur"}  # fmt: skip


async def test_help_assistant_off_by_default(client, as_role):
    _, h = await as_role("trainee")
    set_llm(FakeLLM())
    try:
        r = await client.post("/api/v1/help/ask", json=BODY, headers=h)
    finally:
        set_llm(None)
    assert r.status_code == 409 and r.json()["error"]["code"] == "help_assistant_off"


@pytest.mark.parametrize("fail", [False, True])
async def test_help_assistant_grounded_answer(client, as_role, fail):
    await _flag(client, as_role, True)
    _, h = await as_role("field_responder")
    fake = FakeLLM(fail)
    set_llm(fake)
    help_api._recent.clear()
    try:
        r = await client.post("/api/v1/help/ask", json=BODY, headers=h)
    finally:
        set_llm(None)
    if fail:
        assert r.status_code == 503
        return
    assert r.status_code == 200 and r.json()["answer"].startswith("Open Live")
    system, messages, lang = fake.calls[0]
    assert "ONLY the help text" in system and "Urdu" in system and lang == "ur"
    assert "press the + button" in messages[0]["content"]


async def test_help_assistant_is_throttled(client, as_role):
    await _flag(client, as_role, True)
    _, h = await as_role("trainee")
    set_llm(FakeLLM())
    help_api._recent.clear()
    try:
        codes = [
            (await client.post("/api/v1/help/ask", json=BODY, headers=h)).status_code
            for _ in range(help_api.PER_MINUTE + 1)
        ]
    finally:
        set_llm(None)
    assert codes[:-1] == [200] * help_api.PER_MINUTE and codes[-1] == 429
