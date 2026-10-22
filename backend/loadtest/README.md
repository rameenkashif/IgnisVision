# Load test

`run.py` checks the SRS §5.1.1 / HANDOFF §12 targets against a running stack, using the seeded demo commander:

| Scenario | Target |
|---|---|
| 10 concurrent users signing in and loading pages/API | p95 ≤ 3 s, no errors |
| 5 concurrent zone-capture sessions (WebSocket, JPEG frames at the target rate) | all sustained |
| Frame sent → commander's map update (`zone.updated`) | p95 ≤ 6 s |
| Thermal image upload finished → results | ≤ 5 s |

```bash
cd backend
.venv/bin/python loadtest/run.py --base https://localhost --password '<demo password>'
# options: --users 10 --captures 5 --duration 60 --uploads 5 --ca caddy-root.crt --json out.json
```

It creates and activates a temporary incident and closes it at the end. The exit code is 0 when every target is met. Results from the development machine are in `docs/DEPLOYMENT.md` §1.
