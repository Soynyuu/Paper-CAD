# Repository Guidelines

## Project Structure & Module Organization
Backend sources live in `backend/`, with geometry under `core/`, API routers in `api/`, services in `services/`, and shared helpers in `models/`/`utils/`. The TypeScript workspace sits in `frontend/`, where `packages/chili` provides the UI shell, `packages/chili-three` renders Three.js scenes, and `frontend/cpp/` houses the WebAssembly core. Keep tests beside the code they verify (e.g., `backend/test_*.py`, `packages/*/__tests__`). Samples, deployment scripts, and docs are stored next to their related modules for quick discovery.

## Build, Test, and Development Commands
- `cd backend && python main.py`: Starts the FastAPI STEP→SVG engine on `http://localhost:8001`.
- `cd backend && pytest`: Runs the backend suite; use targeted scripts such as `python test_polygon_overlap.py` for geometry debugging.
- `cd frontend && npm run dev`: Launches the Rspack dev server with hot reload.
- `cd frontend && npm test`: Executes Jest specs (`--watch` for focused runs).
- `cd frontend && npm run build`: Produces the static bundle in `frontend/dist/`.

## Coding Style & Naming Conventions
Python follows PEP 8 with 4-space indents; run `black backend` before review. TypeScript/JS/CSS/JSON/Markdown files are formatted via `npm run format`. Prefer PascalCase for components, camelCase for functions and variables, and kebab-case for CSS classes. C/C++ in `frontend/cpp/` must use `clang-format --style=Webkit`. Avoid inline comments unless necessary and keep edits scoped to the relevant module.

## Testing Guidelines
Use `pytest` for backend coverage and Jest with `@testing-library` conventions on the frontend. Name tests `test_<feature>.py` or `<Component>.test.ts`, mirroring the module tree. Geometry fixtures belong in `backend/samples/` whenever inputs change. Run suites locally before pushing; capture regressions with new SVG outputs when applicable.

## Commit & Pull Request Guidelines
Commits follow Conventional Commits (`feat:`, `fix:`, `refactor:`) capped at 72 characters, with body details and linked issues. Pull requests should summarize validation commands, mention environment or migration impacts, and include screenshots or SVG diffs when UI or rendering changes occur. Call out deployment or configuration updates explicitly.

## Security & Configuration Tips
Configure the backend through `.env`, honoring `PORT`, `FRONTEND_URL`, and `CORS_ALLOW_ALL`. Frontend builds inject `STEP_UNFOLD_API_URL` and optional `STEP_UNFOLD_WS_URL`; update `.env.*` files or Cloudflare Pages settings before publishing. Use `backend/docker-compose.yml` and `frontend/scripts/deploy` to reproduce CI-like environments securely.
