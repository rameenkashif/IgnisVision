import asyncio
import io
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from sqlalchemy import update

from app.db.engine import SessionLocal
from app.ml.mock.models import MockThermalPose
from app.models import Zone


def _seed_with_people(min_people=2) -> int:
    pose = MockThermalPose()
    for seed in range(200):
        img = np.random.default_rng(seed).integers(0, 255, (240, 320, 3), dtype=np.uint8)
        if len(pose.predict(img)) >= min_people:
            return seed
    raise AssertionError("no seed")


def png(seed: int) -> bytes:
    arr = np.random.default_rng(seed).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def mp4(seconds=3, fps=10) -> bytes:
    """Mostly-static scene (so mock detections are stable enough to track) with a little noise."""
    path = Path(tempfile.mkdtemp()) / "t.mp4"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    base = np.random.default_rng(_seed_with_people()).integers(
        0, 255, (240, 320, 3), dtype=np.uint8
    )
    for i in range(seconds * fps):
        frame = base.copy()
        frame[:4, :4] = i  # tiny change; the coarse mock seed ignores it
        w.write(frame)
    w.release()
    return path.read_bytes()


async def wait_job(client, h, job_id, seconds=30):
    for _ in range(int(seconds / 0.1)):
        j = (await client.get(f"/api/v1/jobs/{job_id}", headers=h)).json()
        if j["status"] in ("done", "failed"):
            return j
        await asyncio.sleep(0.1)
    raise AssertionError("job did not finish")


async def _active(client, h, create_incident, responders=()):
    inc = await create_incident(h, list(responders))
    await client.post(f"/api/v1/incidents/{inc['id']}/activate", headers=h)
    return inc


async def test_image_upload_produces_ranked_victims(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    inc = await _active(client, h, create_incident)
    seed = _seed_with_people()
    r = await client.post(
        f"/api/v1/incidents/{inc['id']}/thermal-uploads",
        files={"file": ("t.png", png(seed), "image/png")},
        headers=h,
    )
    assert r.status_code == 202, r.text
    job = await wait_job(client, h, r.json()["job_id"])
    assert job["status"] == "done" and job["progress"] == 1.0 and job["model_version"]

    victims = (await client.get(f"/api/v1/incidents/{inc['id']}/victims", headers=h)).json()
    assert len(victims) >= 2
    scores = [v["rpi_score"] for v in victims]
    assert scores == sorted(scores, reverse=True)
    assert all(v["source"] == "web_upload" and v["media_url"] for v in victims)
    assert all(v["env_risk"] is None for v in victims)  # untagged upload → R unavailable

    dets = (await client.get(f"/api/v1/media/{r.json()['media_id']}/detections", headers=h)).json()
    assert len(dets) == len(victims) and all(len(d["bbox"]) == 4 for d in dets)
    uploads = (await client.get(f"/api/v1/incidents/{inc['id']}/thermal-uploads", headers=h)).json()
    assert uploads[0]["people"] == len(victims) and uploads[0]["job"]["status"] == "done"
    thumb = await client.get(uploads[0]["thumbnail_url"])
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"
    d = (await client.get(f"/api/v1/incidents/{inc['id']}", headers=h)).json()
    assert d["kpis"]["victims_detected"] == len(victims)


async def test_zone_tag_supplies_env_risk_and_critical_alert(client, as_role, create_incident):
    from datetime import UTC, datetime

    _, h = await as_role("incident_commander")
    inc = await _active(client, h, create_incident)
    zone = inc["zones"][0]
    async with SessionLocal() as db:  # zone currently unsafe → R = 1.0
        await db.execute(
            update(Zone)
            .where(Zone.id == zone["id"])
            .values(current_status="unsafe", status_updated_at=datetime.now(UTC))
        )
        await db.commit()
    r = await client.post(
        f"/api/v1/incidents/{inc['id']}/thermal-uploads",
        files={"file": ("t.png", png(_seed_with_people()), "image/png")},
        data={"zone_id": zone["id"]},
        headers=h,
    )
    await wait_job(client, h, r.json()["job_id"])
    victims = (await client.get(f"/api/v1/incidents/{inc['id']}/victims", headers=h)).json()
    assert all(v["env_risk"] == 1.0 and v["zone_code"] == "F1-Z1" for v in victims)
    if any(v["rpi_band"] == "critical" for v in victims):
        alerts = (await client.get(f"/api/v1/incidents/{inc['id']}/alerts", headers=h)).json()
        assert "victim_critical" in [a["type"] for a in alerts["items"]]


async def test_video_upload_samples_and_tracks(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    inc = await _active(client, h, create_incident)
    r = await client.post(
        f"/api/v1/incidents/{inc['id']}/thermal-uploads",
        files={"file": ("t.mp4", mp4(), "video/mp4")},
        headers=h,
    )
    assert r.status_code == 202, r.text
    job = await wait_job(client, h, r.json()["job_id"])
    assert job["status"] == "done", job
    dets = (await client.get(f"/api/v1/media/{r.json()['media_id']}/detections", headers=h)).json()
    frames = sorted({d["frame_index"] for d in dets})
    assert frames == [0, 5, 10, 15, 20, 25]  # 10 fps video sampled at 2 fps
    assert {d["timestamp_ms"] for d in dets} == {0, 500, 1000, 1500, 2000, 2500}
    victims = (await client.get(f"/api/v1/incidents/{inc['id']}/victims", headers=h)).json()
    per_frame = len(dets) // len(frames)
    assert len(victims) == per_frame  # same people across samples → one victim each
    # Sampled frames are stored and served (playable whatever the upload's codec)
    samples = (await client.get(f"/api/v1/media/{r.json()['media_id']}/frames", headers=h)).json()
    assert [f["frame_index"] for f in samples] == frames
    img = await client.get(samples[2]["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert dets[0]["frame_url"] and victims[0]["frame_url"]


async def test_mark_victim_rescued_moves_it_down(client, as_role, create_incident):
    _, h = await as_role("incident_commander")
    inc = await _active(client, h, create_incident)
    r = await client.post(
        f"/api/v1/incidents/{inc['id']}/thermal-uploads",
        files={"file": ("t.png", png(_seed_with_people()), "image/png")},
        headers=h,
    )
    await wait_job(client, h, r.json()["job_id"])
    victims = (await client.get(f"/api/v1/incidents/{inc['id']}/victims", headers=h)).json()
    top = victims[0]["id"]
    r = await client.patch(f"/api/v1/victims/{top}", json={"status": "rescued"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "rescued"
    victims = (await client.get(f"/api/v1/incidents/{inc['id']}/victims", headers=h)).json()
    assert victims[-1]["id"] == top


async def test_upload_validation_and_access(client, as_role, make_user, login, create_incident):
    _, h = await as_role("incident_commander")
    inc = await _active(client, h, create_incident)
    url = f"/api/v1/incidents/{inc['id']}/thermal-uploads"
    r = await client.post(url, files={"file": ("x.txt", b"hello", "text/plain")}, headers=h)
    assert r.status_code == 415
    r = await client.post(url, files={"file": ("x.png", b"not a png", "image/png")}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "unreadable_media"
    responder = await make_user("field_responder")
    h_r = await login(responder)
    r = await client.post(url, files={"file": ("t.png", png(1), "image/png")}, headers=h_r)
    assert r.status_code == 202  # any responder may upload to an active incident
    trainee = await make_user("trainee")
    h_t = await login(trainee)
    r = await client.post(url, files={"file": ("t.png", png(1), "image/png")}, headers=h_t)
    assert r.status_code == 403
    media_id = (await client.get(url, headers=h)).json()[0]["media_id"]
    assert (
        await client.get(f"/api/v1/media/{media_id}/detections", headers=h_t)
    ).status_code == 403
    await client.post(f"/api/v1/incidents/{inc['id']}/close", json={"confirm": True}, headers=h)
    r = await client.post(url, files={"file": ("t.png", png(1), "image/png")}, headers=h)
    assert r.status_code == 409
