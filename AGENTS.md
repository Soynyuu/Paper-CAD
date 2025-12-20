# Repository Guidelines

## Project Structure & Module Organization
- **Root layout**: `frontend/` (TypeScript app + WASM), `backend/` (FastAPI services), `docs/` (deployment + optimization reports). Keep shared assets under their current directories; avoid mixing languages within a single package.
- **Frontend workspaces**: `frontend/packages/chili-*` hold feature modules (UI, Three.js, core logic). Place new Web Components in the relevant package and wire them through `chili-web`'s entry point.
- **Backend layers**: `backend/core` handles unfolding algorithms, `services/` orchestrates workflows, and `api/endpoints.py` wires HTTP routes. Tests sit beside their domains under `backend/tests` or package-specific `__tests__` directories.

## Build, Test, and Development Commands
- `cd backend && python main.py` — run the FastAPI dev server on `localhost:8001` (use `ENV=demo` for optimized local demos).
- `cd frontend && npm run dev` — Rspack dev server with hot reload on `localhost:8080`; `npm run demo` serves the optimized build locally.
- `npm run build` (frontend) and `docker compose up -d` (backend) mirror production bundles.

## Coding Style & Naming Conventions
- **TypeScript/C++**: 2-space indentation, ES module syntax, PascalCase for components, camelCase for utilities. Run `npm run format` (Prettier + clang-format) before committing.
- **Python**: 4-space indentation, prefer descriptive snake_case. Use `black .` from `backend/` as the canonical formatter.
- Shared naming prefixes (`chili-`, `step_`) should stay consistent when adding new packages or modules.

## Testing Guidelines
- Frontend tests run via `cd frontend && npm test`; colocate specs under `__tests__` or `*.test.ts`. Mock WASM-heavy dependencies when possible.
- Backend tests use `cd backend && pytest [-k pattern]`; larger scenarios live under `tests/citygml`. Keep fixtures lightweight and document any OCCT requirements in docstrings.

## Commit & Pull Request Guidelines
- Follow the existing verb-style prefixes (`feat:`, `fix:`, `docs:`, `chore:`) as seen in `git log`. Scope the subject to 72 characters.
- PRs should summarize motivation, list major changes, mention affected packages (`frontend/chili-ui`, `backend/core`, etc.), and link issues. Attach screenshots or SVG samples when UI or unfold output changes.
- Ensure formatters and tests pass locally before requesting review; include reproduction steps for bugs or performance regressions.
