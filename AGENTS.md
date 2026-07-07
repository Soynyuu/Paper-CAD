# Repository Guidelines

## Project Structure & Module Organization
Paper-CAD is a browser CAD for turning 3D building models into printable SVG/PDF unfoldings.

- `backend/`: Python 3.10 FastAPI service. API routes live in `api/`, request/response schemas in `models/`, core unfolding/export logic in `core/`, PLATEAU/CityGML integrations in `services/`, and pytest tests in `tests/`.
- `frontend/`: main TypeScript CAD app using npm workspaces under `packages/*`. C++/WASM sources are in `cpp/`; generated builds go to `dist/`.
- `lp/`: standalone Vite/React landing page. Follow `lp/AGENTS.md` for scoped landing-page work.
- `docs/` and root markdown files contain design, deployment, and planning notes.

## Build, Test, and Development Commands
- `cd backend && conda env create -f environment.yml`: create the backend environment.
- `cd backend && conda activate paper-cad && python main.py`: run the API at `http://localhost:8001`.
- `cd backend && pytest`: run backend tests; use `pytest tests/citygml/streaming/` for the streaming subset.
- `cd frontend && npm install`: install workspace dependencies.
- `cd frontend && npm run dev`: run the CAD frontend at `http://localhost:8080`.
- `cd frontend && npm run build`: production Rspack build.
- `cd frontend && npm test` or `npm run testc`: run Jest tests; `testc` includes coverage.
- `cd frontend && npm run format`: run Prettier and clang-format.
- `cd lp && npm run dev|build|lint|preview`: develop, build, lint, or preview the landing page.

## Coding Style & Naming Conventions
Python code follows PEP 8 with 4-space indentation, typed Pydantic models, and FastAPI router boundaries. Keep geometry changes localized to `backend/core/` or `backend/services/citygml/` as appropriate.

TypeScript uses strict mode, 4-space Prettier formatting (`frontend/.prettierrc`), camelCase variables, PascalCase React components/classes, and `*.module.css` for CSS modules. C/C++ formatting is clang-format with WebKit style.

## Testing Guidelines
Place backend tests as `backend/tests/test_*.py`. Place frontend Jest tests as `*.test.ts` or `*.test.tsx` inside package `test/` directories. Add regression coverage for geometry, unfolding, CityGML parsing, and import/export changes.

## Commit & Pull Request Guidelines
Use Conventional Commits, as in recent history: `feat: ...`, `fix: ...`, `chore: ...`, `test: ...`, `docs: ...`. Branch names should follow `feat/name`, `fix/name`, `docs/name`, `refactor/name`, or `test/name`.

PRs should include a concise summary, linked issues such as `Closes #123`, test results, and screenshots for UI changes. Note environment or data requirements for PLATEAU/CityGML work.

## Security & Configuration Tips
Do not commit secrets or local `.env.production` files. Use documented variables such as `PORT`, `FRONTEND_URL`, `CORS_ALLOW_ALL`, and `STEP_UNFOLD_API_URL`; keep permissive CORS settings limited to development.
