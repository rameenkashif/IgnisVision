# Ignis Vision

Pakistan's first AI-powered fire safety and intelligence system — dual-camera (RGB + thermal) zone classification and victim detection for fire incident commanders. FYP, CSE Dept, BESE 29.

## Frontend

React + TypeScript + Vite. Currently implements the app entry flow:

- **Splash** — animated logo intro (`/`)
- **Login** — mock UI, no auth wired up yet (`/login`)
- **Language select** — English / Urdu, persisted and applied app-wide (`/language`)
- **Dashboard** — placeholder; the full Commander Dashboard (live monitoring, zone map, alerts) is being rebuilt next (`/dashboard`)

Design tokens (colors, fonts) live in `src/styles/theme.css`, carried over from the original dashboard mockup.

### Setup

```bash
npm install
npm run dev
```

### Build

```bash
npm run build
```
