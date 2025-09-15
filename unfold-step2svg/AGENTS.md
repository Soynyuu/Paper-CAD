# Repository Guidelines

## Project Structure & Module Organization
- `core/`: Unfold pipeline (e.g., `file_loaders.py`, `geometry_analyzer.py`, `unfold_engine.py`, `layout_manager.py`, `svg_exporter.py`, `step_exporter.py`).
- `api/`: FastAPI routes (`endpoints.py`). App factory and CORS in `config.py`; entrypoint in `main.py`.
- `services/`: STEP processing helpers (`step_processor.py`).
- `models/`, `utils/`: Shared types/utilities as needed.
- Root: deployment (`Dockerfile`, `docker-compose.yml`, `Containerfile`, `nginx/`), env files (`.env.development`, `.env.production`), docs (`API_REFERENCE.md`).
- Tests/examples: `test_*.py`, `test_*.sh`, sample outputs.

## Build, Test, and Development Commands
- Create env: `conda env create -f environment.yml && conda activate unfold-step2svg`.
- Run API (dev): `python main.py` (serves on `:8001`).
- Health check: `curl http://localhost:8001/api/health`.
- Docker (optional): `docker build -t unfold-step2svg .` then `docker compose up -d`.
- Run tests/examples: `python test_polygon_overlap.py`, `bash test_layout_modes.sh`, `python test_brep_export.py`.

## Coding Style & Naming Conventions
- Python 3.10, follow PEP 8; 4-space indent; use type hints.
- Files/modules/functions: `snake_case`; classes: `CamelCase`.
- Keep modules focused (I/O in `file_loaders`, geometry in `geometry_analyzer`, layout in `layout_manager`, export in `svg_exporter`/`step_exporter`).
- Docstrings for public functions; log concise messages (avoid noisy prints in core loops).

## Testing Guidelines
- Prefer small, focused tests near root: `test_*.py` executable via `python test_xyz.py`.
- Add scenario scripts when helpful: `test_*.sh` for end-to-end checks.
- Include minimal sample inputs (e.g., small `.step`) and verify SVG/placement where feasible.
- When adding geometry/layout logic, cover edge cases: overlaps, containment, edge touching.

## Commit & Pull Request Guidelines
- Commits: clear, imperative subject (e.g., "fix: handle edge-touching polygons").
- PRs: description of change, rationale, before/after (attach SVG screenshots when visual), steps to reproduce, related issues.
- Ensure `python main.py` runs and health check passes; update `API_REFERENCE.md` when endpoints change.

## Security & Configuration Tips
- Configure via `.env.development` / `.env.production` (e.g., `PORT`, `FRONTEND_URL`).
- OCCT is required for full features; code should degrade gracefully if unavailable.
- Avoid committing large binaries; place samples under a dedicated folder and keep small.
