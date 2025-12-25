# Repository Guidelines

## Project Structure and Module Organization
Paper-CAD is a split frontend/backend repo with shared docs:
- `frontend/`: TypeScript monorepo (npm workspaces) under `frontend/packages/` with app (`chili-web`), UI (`chili-ui`), core logic (`chili-core`), and 3D (`chili-three`). WebAssembly sources are in `frontend/cpp/`.
- `backend/`: FastAPI service. Core pipeline is in `backend/core/`, routes in `backend/api/`, helpers in `backend/services/` (CityGML tooling), and tests in `backend/tests/`.
- `docs/`: Deployment and optimization notes.

## Build, Test, and Development Commands
Frontend (run from `frontend/`):
- `npm install`: install workspace dependencies.
- `npm run dev`: start dev server at `http://localhost:8080`.
- `npm run demo`: demo build served locally.
- `npm run build`: production build.
- `npm run build:wasm`: build the C++ WebAssembly module.
- `npm test` or `npm run testc`: run Jest tests (with coverage in `testc`).
- `npm run format`: run Prettier and clang-format.

Backend (run from `backend/`):
- `conda env create -f environment.yml` then `conda activate paper-cad`: create/activate env.
- `python main.py`: start API at `http://localhost:8001`.
- `ENV=demo python main.py`: demo-mode backend.
- `pytest`: run unit tests (see `backend/tests/`).
- `docker compose up -d`: run via container.

## Coding Style and Naming Conventions
- TypeScript/JS/CSS/JSON/MD are formatted with Prettier (`tabWidth: 4`).
- C/C++ in `frontend/cpp/` uses clang-format (Webkit style) via `npm run format`.
- Python follows PEP 8 with 4-space indentation; use `black .` if you are formatting Python code.
- Naming patterns: workspace packages use `chili-*`, frontend tests use `*.test.ts`, and Python tests use `test_*.py`.

## Testing Guidelines
- Frontend: Jest tests live in `frontend/packages/*/test/*.test.ts`. Run `npm test` or `npm run testc`.
- Backend: pytest tests live under `backend/tests/`. Run `pytest` or target a folder such as `pytest tests/citygml/streaming/`.
- Manual API checks are available via `http://localhost:8001/docs` once the backend is running.

## Commit and Pull Request Guidelines
- Commit history mostly follows conventional prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `perf:`, `chore:`) with short, imperative subjects. Use that pattern when possible.
- PRs should include a concise summary, rationale, and test steps. Link related issues, and attach screenshots for UI changes or SVG output changes when relevant.

## Configuration Notes
- Frontend config is build-time: set `STEP_UNFOLD_API_URL` (required) and `STEP_UNFOLD_WS_URL` (optional) in `.env.development`, `.env.demo`, or `.env.production.example`.
- Backend config uses `.env.development`, `.env.demo`, or `.env.production` with `PORT`, `FRONTEND_URL`, and `CORS_ALLOW_ALL`.

## CityGML Conversion Phases (AI Safety Note)
- **PHASE:0** Coordinate recentering to avoid precision loss.
- **PHASE:1** XLink index build before any geometry extraction.
- **PHASE:2-6** LOD extraction → geometry build → validation.
- **PHASE:7** STEP export.
