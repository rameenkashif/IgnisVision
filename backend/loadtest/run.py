"""Load test for the non-functional targets (HANDOFF §12, SRS §5.1.1).

Runs against a live stack (Docker Compose) and checks:
  A. 10 concurrent users: sign-in and page/API requests respond in ≤ 3 s (p95).
  B. 5 concurrent zone-capture sessions (WebSocket, JPEG frames at the target rate) are
     sustained, and the commander's map gets each update ≤ 6 s after the frame is sent (p95).
  C. An uploaded thermal image has results ≤ 5 s after the upload finishes.
A and B run at the same time (the realistic case); C runs afterwards.

    cd backend
    .venv/bin/python loadtest/run.py --base https://localhost --password '<demo password>'

Exit code 0 when every target is met. Uses the seeded demo accounts (commander1).
"""

import argparse
import asyncio
import io
import json
import ssl
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np
import websockets
from PIL import Image


@dataclass
class Stats:
    samples: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, name: str, ms: float) -> None:
        self.samples[name].append(ms)

    @staticmethod
    def p(values: list[float], q: float) -> float:
        if not values:
            return float("nan")
        return sorted(values)[min(len(values) - 1, int(round(q * (len(values) - 1))))]

    def table(self) -> list[dict]:
        return [
            {
                "name": k,
                "n": len(v),
                "p50_ms": round(statistics.median(v)),
                "p95_ms": round(self.p(v, 0.95)),
                "max_ms": round(max(v)),
                "errors": self.errors.get(k, 0),
            }
            for k, v in sorted(self.samples.items())
        ]


def jpeg(seed: int, w: int = 960, h: int = 640) -> bytes:
    """A textured indoor-ish frame (bands for ceiling/wall/floor, noise so it is analysable)."""
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.float32)
    img[: h // 5] = (198, 198, 204)
    img[h // 5 : int(h * 0.75)] = (214, 200, 176)
    img[int(h * 0.75) :] = (150, 122, 92)
    img += rng.normal(0, 8, img.shape)
    buf = io.BytesIO()
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(buf, "JPEG", quality=80)
    return buf.getvalue()


def png(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    buf = io.BytesIO()
    Image.fromarray(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)).save(buf, "PNG")
    return buf.getvalue()


async def login(client: httpx.AsyncClient, username: str, password: str, stats: Stats) -> str:
    t0 = time.perf_counter()
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    stats.add("POST /auth/login", (time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        stats.errors["POST /auth/login"] += 1
        raise RuntimeError(f"login {username}: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


async def setup_incident(client: httpx.AsyncClient, token: str, zones: int) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/v1/incidents",
        json={"address": "Load test, Mall Road", "floors": 1, "zones_per_floor": zones},
        headers=h,
    )
    r.raise_for_status()
    inc = r.json()
    (await client.post(f"/api/v1/incidents/{inc['id']}/activate", headers=h)).raise_for_status()
    return inc


async def close_incident(client: httpx.AsyncClient, token: str, inc_id: str) -> None:
    await client.post(
        f"/api/v1/incidents/{inc_id}/close",
        json={"confirm": True},
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------- A: concurrent users


async def http_user(args, n: int, inc_id: str, stats: Stats, stop: float) -> None:
    async with httpx.AsyncClient(base_url=args.base, verify=args.verify, timeout=30) as c:
        token = await login(c, args.user, args.password, stats)
        h = {"Authorization": f"Bearer {token}"}
        paths = [
            ("GET / (app)", "/", False),
            ("GET /auth/me", "/api/v1/auth/me", True),
            ("GET /incidents", "/api/v1/incidents?status=active&status=dispatched", True),
            ("GET /incidents/{id}", f"/api/v1/incidents/{inc_id}", True),
            ("GET /incidents/{id}/alerts", f"/api/v1/incidents/{inc_id}/alerts", True),
            ("GET /incidents/{id}/victims", f"/api/v1/incidents/{inc_id}/victims", True),
            ("GET /reports list", "/api/v1/incidents?status=closed&limit=200", True),
            ("GET /settings", "/api/v1/settings", True),
        ]
        i = 0
        while time.monotonic() < stop:
            name, path, auth = paths[(i + n) % len(paths)]
            t0 = time.perf_counter()
            try:
                r = await c.get(path, headers=h if auth else None)
                ok = r.status_code < 400
            except httpx.HTTPError:
                ok = False
            stats.add(name, (time.perf_counter() - t0) * 1000)
            if not ok:
                stats.errors[name] += 1
            i += 1
            if i % 40 == 0:  # sign in again now and then, so sign-in is measured under load
                token = await login(c, args.user, args.password, stats)
                h = {"Authorization": f"Bearer {token}"}
            await asyncio.sleep(args.think)


# ---------------------------------------------------------------- B: capture sessions


def ws_url(base: str, path: str) -> str:
    return base.replace("https://", "wss://").replace("http://", "ws://") + path


async def commander_watch(args, token: str, inc_id: str, sent: dict, stats: Stats, stop: float):
    """Measures frame sent → zone.updated on the commander channel (the map update)."""
    async with websockets.connect(
        ws_url(args.base, f"/ws/incidents/{inc_id}"), ssl=args.ssl, max_size=None
    ) as ws:
        await ws.send(json.dumps({"type": "auth", "token": token}))
        while time.monotonic() < stop + 10:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            except TimeoutError:
                continue
            if msg.get("type") == "zone.updated" and msg.get("zone_id") in sent:
                t_sent = sent[msg["zone_id"]]
                if t_sent:
                    stats.add(
                        "frame → commander map (zone.updated)",
                        (time.perf_counter() - t_sent) * 1000,
                    )
                    sent[msg["zone_id"]] = None


async def capture_session(args, token, zone, sent, stats, stop, health) -> None:
    name = "frame → zone_result (phone)"
    frames = [jpeg(hash(zone["id"]) % 1000 + k) for k in range(3)]
    async with websockets.connect(
        ws_url(args.base, "/ws/capture"), ssl=args.ssl, max_size=None
    ) as ws:
        await ws.send(json.dumps({"type": "auth", "token": token}))
        await ws.send(json.dumps({"type": "start", "zone_id": zone["id"]}))
        started = None
        while started is None:
            m = json.loads(await ws.recv())
            if m.get("type") == "started":
                started = m
            elif m.get("type") == "error":
                raise RuntimeError(f"capture start: {m}")
        period = 1.0 / float(started.get("target_fps") or 1.0)
        pending: list[float] = []

        async def reader():
            while True:
                m = await ws.recv()
                if isinstance(m, bytes):
                    continue
                m = json.loads(m)
                if m.get("type") == "zone_result":
                    health["results"] += 1
                    if pending:
                        t0 = pending.pop()  # latest-frame-wins: older frames may be skipped
                        pending.clear()
                        stats.add(name, (time.perf_counter() - t0) * 1000)
                elif m.get("type") == "error":
                    stats.errors[name] += 1

        task = asyncio.create_task(reader())
        k = 0
        try:
            while time.monotonic() < stop:
                t0 = time.perf_counter()
                await ws.send(frames[k % len(frames)])
                health["frames"] += 1
                pending.append(t0)
                if sent.get(zone["id"]) is None:
                    sent[zone["id"]] = t0
                k += 1
                await asyncio.sleep(max(0.0, period - (time.perf_counter() - t0)))
            await ws.send(json.dumps({"type": "stop"}))
            await asyncio.sleep(1.5)
        finally:
            task.cancel()
        health["sessions_ok"] += 1


# ---------------------------------------------------------------- C: thermal upload


async def thermal(args, token: str, inc_id: str, stats: Stats) -> None:
    h = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=args.base, verify=args.verify, timeout=60) as c:
        for k in range(args.uploads):
            r = await c.post(
                f"/api/v1/incidents/{inc_id}/thermal-uploads",
                files={"file": (f"t{k}.png", png(k), "image/png")},
                headers=h,
            )
            if r.status_code != 202:
                stats.errors["thermal upload → results"] += 1
                continue
            t_done_upload = time.perf_counter()
            job = r.json()["job_id"]
            while True:
                j = (await c.get(f"/api/v1/jobs/{job}", headers=h)).json()
                if j["status"] in ("done", "failed"):
                    break
                await asyncio.sleep(0.1)
            stats.add("thermal upload → results", (time.perf_counter() - t_done_upload) * 1000)
            if j["status"] != "done":
                stats.errors["thermal upload → results"] += 1


async def main(args) -> int:
    stats = Stats()
    async with httpx.AsyncClient(base_url=args.base, verify=args.verify, timeout=30) as c:
        token = await login(c, args.user, args.password, Stats())
        inc = await setup_incident(c, token, max(args.captures, 1))
    try:
        stop = time.monotonic() + args.duration
        sent: dict[str, float | None] = {z["id"]: None for z in inc["zones"][: args.captures]}
        health = {"frames": 0, "results": 0, "sessions_ok": 0}
        watcher = asyncio.create_task(commander_watch(args, token, inc["id"], sent, stats, stop))
        await asyncio.sleep(1)
        results = await asyncio.gather(
            *(http_user(args, n, inc["id"], stats, stop) for n in range(args.users)),
            *(
                capture_session(args, token, z, sent, stats, stop, health)
                for z in inc["zones"][: args.captures]
            ),
            return_exceptions=True,
        )
        watcher.cancel()
        failures = [r for r in results if isinstance(r, Exception)]
        await thermal(args, token, inc["id"], stats)
    finally:
        async with httpx.AsyncClient(base_url=args.base, verify=args.verify, timeout=30) as c:
            await close_incident(c, token, inc["id"])

    rows = stats.table()
    width = max(len(r["name"]) for r in rows)
    print(f"\n{'measure':<{width}}  {'n':>5} {'p50':>7} {'p95':>7} {'max':>7} {'err':>4}")
    for r in rows:
        print(f"{r['name']:<{width}}  {r['n']:>5} {r['p50_ms']:>6}ms {r['p95_ms']:>6}ms "
              f"{r['max_ms']:>6}ms {r['errors']:>4}")  # fmt: skip
    print(
        f"\ncapture: {health['sessions_ok']}/{args.captures} sessions sustained, "
        f"{health['frames']} frames sent, {health['results']} results; "
        f"task failures: {failures or 'none'}"
    )

    def p95(name: str) -> float:
        return Stats.p(stats.samples.get(name, []), 0.95)

    http = [r for r in rows if r["name"].startswith(("GET", "POST"))]
    checks = {
        "pages and sign-in p95 ≤ 3 s (10 users)": all(
            r["p95_ms"] <= 3000 and not r["errors"] for r in http
        ),
        "5 capture sessions sustained": health["sessions_ok"] == args.captures and not failures,
        "map update p95 ≤ 6 s": p95("frame → commander map (zone.updated)") <= 6000,
        "thermal image results ≤ 5 s": stats.samples.get("thermal upload → results")
        and max(stats.samples["thermal upload → results"]) <= 5000
        and not stats.errors.get("thermal upload → results"),
    }  # fmt: skip
    print()
    for k, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {k}")
    if args.json:
        summary = json.dumps({"rows": rows, "capture": health, "checks": checks}, indent=2)
        Path(args.json).write_text(summary)  # noqa: ASYNC240 — once, after the run
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="https://localhost")
    ap.add_argument("--user", default="commander1")
    ap.add_argument("--password", required=True)
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--captures", type=int, default=5)
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--think", type=float, default=0.5, help="seconds between a user's requests")
    ap.add_argument("--uploads", type=int, default=5)
    ap.add_argument("--ca", help="CA bundle for the server certificate (e.g. caddy-root.crt)")
    ap.add_argument("--json", help="write the results to this file")
    a = ap.parse_args()
    if a.ca:
        a.verify = a.ca
        a.ssl = ssl.create_default_context(cafile=a.ca)
    else:  # local stack with Caddy's internal CA
        a.verify = False
        a.ssl = ssl.create_default_context()
        a.ssl.check_hostname = False
        a.ssl.verify_mode = ssl.CERT_NONE
    if a.base.startswith("http://"):
        a.ssl = None
    sys.exit(asyncio.run(main(a)))
