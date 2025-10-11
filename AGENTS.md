# Repository Guidelines

Paper-CAD couples a FastAPI unfolding engine with a WebAssembly frontend; the notes below keep both halves aligned.

## Project Structure & Module Organization
- `backend/`: Python service exposing STEP → SVG APIs; core logic lives in `core/`, routers in `api/`, orchestration helpers in `services/`, utility types under `models/` and `utils/`.
- `frontend/`: TypeScript workspace (`packages/*`) for the modeling UI; `packages/chili` drives the app shell, while `packages/chili-three` handles Three.js rendering. WebAssembly sources sit in `frontend/cpp/`.
- Samples, deployment scripts, and docs live beside the modules they support for quick discovery.

## Build, Test, and Development Commands
- `cd backend && conda env create -f environment.yml && conda activate paper-cad`: bootstrap the OCCT-ready runtime.
- `cd backend && python main.py`: run the API at `http://localhost:8001`.
- `cd backend && pytest`: execute unit tests; call focused scripts like `python test_polygon_overlap.py` when iterating on geometry.
- `cd frontend && npm install`: installs workspace dependencies.
- `cd frontend && npm run dev`: starts the Rspack dev server with hot reload.
- `cd frontend && npm test` or `npm run testc`: run Jest suites (optionally with coverage).
- `cd frontend && npm run build`: produces a static bundle in `dist/` for Pages/Edge deployment.

## Coding Style & Naming Conventions
- Python follows PEP 8 with 4-space indents; run `black backend` before PRs and keep modules `snake_case` with type-hinted functions.
- TypeScript/JS/CSS/JSON/Markdown format via `npm run format`; C/C++ in `cpp/` use `clang-format --style=Webkit`. Favor `PascalCase` components, `camelCase` functions, and kebab-case CSS classes.

## Testing Guidelines
- Keep tests near the code (`backend/test_*.py`, frontend specs under `packages/*/__tests__`), naming them `test_<feature>.py` or `<Component>.test.ts` for quick grepability.
- Cover new logic with pytest or Jest and add fixtures in `backend/samples/` whenever geometry inputs change.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `refactor:`) as seen in recent history and keep summaries under 72 chars with detail in the body.
- PRs must link issues, list validation commands, and include screenshots or SVG diffs when visuals shift; call out env or migration changes explicitly.

## Environment & Configuration Tips
- Configure the backend via `.env` or env vars (`PORT`, `FRONTEND_URL`, `CORS_ALLOW_ALL`) and document defaults when changing behavior.
- Frontend builds bake in `STEP_UNFOLD_API_URL` and optional `STEP_UNFOLD_WS_URL`; update `.env.*` or Cloudflare Pages settings before `npm run build`.
- Use container workflows (`backend/docker-compose.yml`, `frontend/scripts/deploy`) to reproduce environments in CI or remote previews.
