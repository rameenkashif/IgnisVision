# End-to-end demo (HANDOFF §14)

The whole flow with mock models. It is also an automated Playwright test, `frontend/e2e/demo.spec.ts`, which CI runs on every push.

## Setup

```bash
cp .env.example .env    # set POSTGRES_PASSWORD, JWT_SECRET; for the demo also MOCK_SCENARIO=escalating
docker compose up -d --build
docker compose exec -e SEED_PASSWORD=Demo-pass-1234 backend python -m app.db.seed
```

Open **https://localhost** (trust Caddy's certificate, README). Use a desktop browser for the commander and a phone (or a second browser at phone size, with a webcam) for the responder.

## Steps

1. **Admin** signs in as `admin`. **Administration → Users → New user**: a commander and two field responders. Each gets a temporary password, shown once. Switch the language to **اردو**: the whole interface turns right to left. Switch back.
2. **Commander** signs in with the new account and is asked to choose a new password. **Live monitoring → + Log new emergency**: address, 2 floors × 4 zones, both responders assigned to zones. **Dispatch team & create incident** shows the briefing; **Teams on site — start live monitoring** goes live. All zones start **Unclassified**.
3. **Responder** signs in on the phone (new password too) and lands on **Zone capture**. Their zone is first (★). **Start capture**: within a few seconds the commander's zone changes colour. With `MOCK_SCENARIO=escalating` it goes safe → caution → unsafe; a critical "changed rapidly" alert appears at the top of the dashboard and is spoken, and the phone says "Turn back". **Stop capture**.
4. **Commander → Thermal & image analysis**: choose a zone, upload `frontend/e2e/fixtures/thermal.mp4`. Progress shows, then people appear with posture and priority. Back on **Live monitoring**, the ranked list has the critical person first and a critical alert.
5. **Mobile sync**: the mobile app (or the test helper) posts `POST /api/v1/sync/incidents` linked to the incident; its people appear with source **Mobile**. Posting the same payload again creates nothing new.
6. **Close incident** → confirm. **Incident reports** has the report; **PDF (English)** and **PDF (اردو)** download.
7. **Trainee** (`trainee1`) opens a scenario in the **Training simulator**, labels every region, submits, and sees the score, the correct answers and the model's output. **Training staff** (`trainer1`) see the attempt under **Trainee results**.
8. A trainee calling `GET /api/v1/incidents` gets **403**.
9. **Admin → Administration → System status** shows **Mock models** with each model's version.

When all of this passes, the remaining work is the real model adapters (`docs/MODEL_INTEGRATION.md`).

## Run the automated version

```bash
cd frontend
E2E_PASSWORD=Demo-pass-1234 npx playwright test e2e/demo.spec.ts      # just the demo
E2E_PASSWORD=Demo-pass-1234 npx playwright test                       # everything
```

`E2E_DOCKER_RESTART=1` also runs the backend-restart test (it restarts the backend container).
