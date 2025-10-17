# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI STEP→SVG engine; keep geometry in `core/`, API routers under `api/`, services in `services/`, types in `models/` and `utils/`.
- `frontend/`: TypeScript workspace; `packages/chili` hosts the shell, `packages/chili-three` renders Three.js views, and `frontend/cpp/` compiles the WebAssembly core.
- Tests live beside code (`backend/test_*.py`, `packages/*/__tests__`), while samples, deployment scripts, and docs sit next to the modules they support for quick discovery.

## Build, Test, and Development Commands
- `cd backend && python main.py`: Launches the API at `http://localhost:8001`.
- `cd backend && pytest`: Runs the backend suite; use targeted scripts like `python test_polygon_overlap.py` when iterating on geometry.
- `cd frontend && npm run dev`: Starts the Rspack dev server with hot reload.
- `cd frontend && npm test`: Executes Jest specs; add `--watch` for focused cycles.
- `cd frontend && npm run build`: Produces the static bundle in `frontend/dist/`.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents in Python; run `black backend` before reviewing.
- TypeScript, JS, CSS, JSON, and Markdown format through `npm run format`; prefer PascalCase components, camelCase functions, and kebab-case classes.
- C/C++ sources in `frontend/cpp/` use `clang-format --style=Webkit`.

## Testing Guidelines
- Backend tests rely on `pytest`; frontend uses Jest with `@testing-library` conventions.
- Name tests `test_<feature>.py` or `<Component>.test.ts`; keep fixtures in `backend/samples/` when geometry inputs change.
- Run suites locally before PRs and capture regressions from newly generated SVGs.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `refactor:`) capped at 72 characters with details in the body.
- Link issues, summarize validation commands, and include relevant screenshots or SVG diffs when visuals shift.
- Call out environment updates, migrations, or deployment impacts explicitly in the PR description.

## Environment & Configuration Tips
- Configure the backend via `.env`, honoring `PORT`, `FRONTEND_URL`, and `CORS_ALLOW_ALL` defaults.
- Frontend builds inject `STEP_UNFOLD_API_URL` and optional `STEP_UNFOLD_WS_URL`; update `.env.*` or Cloudflare Pages settings before publishing.
- Use `backend/docker-compose.yml` and `frontend/scripts/deploy` to reproduce CI-like environments when debugging.
