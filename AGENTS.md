# Repository Guidelines

## Project Structure & Module Organization
`frontend/` is a TypeScript monorepo (Rspack) with `packages/chili-*` modules; the app entry is `frontend/packages/chili-web/`, and the C++ CAD kernel lives in `frontend/cpp/` for WASM builds. `backend/` hosts the FastAPI service with the unfold pipeline in `core/`, API routes in `api/`, and services in `services/`. Tests live in `frontend/packages/*/test/` and `backend/tests/`. Operational docs are in `docs/`, and `lp/` contains landing page assets.

## Build, Test, and Development Commands
Run commands from the directory shown:
```bash
cd backend
conda env create -f environment.yml
conda activate paper-cad
python main.py            # API http://localhost:8001
ENV=demo python main.py   # demo mode
pytest                    # backend tests
```
```bash
cd frontend
npm install
npm run dev               # UI http://localhost:8080
npm run build             # production build
npm run build:wasm         # build C++ WASM kernel
npm test                  # Jest tests
npm run format            # Prettier + clang-format
```
Other useful commands: `npm run demo`, `npm run testc` (coverage), `npm run deploy:production` (Cloudflare Pages), and `docker compose up -d` from `backend/` for backend deployment.

## Coding Style & Naming Conventions
TypeScript/JS/CSS/JSON/MD are formatted by Prettier (2-space indentation). C++ uses clang-format with Webkit style (`npm run format`). Python follows existing 4-space indentation and PEP8-like conventions. Packages use `chili-*` naming, components are PascalCase, and variables are camelCase. Tests are named `*.test.ts(x)` (frontend) and `test_*.py` (backend).

## Testing Guidelines
Frontend uses Jest; tests live under `frontend/packages/*/test/` (example: `npm test -- packages/chili-core/test/observer.test.ts`). Backend uses pytest; tests live under `backend/tests/` (example: `pytest tests/citygml/streaming/ -v`). There is no explicit coverage target, but add regression tests for geometry or export changes.

## Commit & Pull Request Guidelines
Commit history favors conventional prefixes like `feat:`, `fix:`, and `docs:` with short, imperative summaries. Avoid `wip` commits in shared branches. PRs should include a clear summary, rationale, test results, and screenshots/GIFs for UI or SVG output changes, plus linked issues when applicable.

## Configuration & Environment
Frontend build-time env vars: `STEP_UNFOLD_API_URL` (required) and `STEP_UNFOLD_WS_URL` (optional) via `.env.*`. Backend runtime env vars: `PORT`, `FRONTEND_URL`, `CORS_ALLOW_ALL` via `.env.*`. Prereqs: Node.js 18+ and Python 3.10 (Conda recommended).
