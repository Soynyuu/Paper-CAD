# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paper-CAD is a web-based CAD tool for creating 3D building models and converting them to 2D papercraft templates (展開図/unfold diagrams).

- **Frontend**: TypeScript monorepo with Web Components, Three.js, Cesium 3D Tiles, and WebAssembly CAD kernel
- **Backend**: FastAPI (Python) with OpenCASCADE for STEP file processing and unfolding

## Development Commands

### Frontend (from `/frontend`)

```bash
npm install              # Install dependencies (run from workspace root)
npm run dev              # Dev server on http://localhost:8080
npm run build            # Production build
npm run demo             # Production build served locally (for demos)
npm run build:wasm       # Build C++ WebAssembly module
npm test                 # Run Jest tests
npm run testc            # Tests with coverage
npm run format           # Prettier + clang-format

# Run single test file
npm test -- packages/chili-core/test/observer.test.ts

# Deployment (Cloudflare Pages)
npm run deploy:production
```

### Backend (from `/backend`)

```bash
conda activate paper-cad
python main.py           # API server on http://localhost:8001
ENV=demo python main.py  # Demo mode

pytest                   # Run all tests
pytest -v tests/citygml/streaming/test_parser.py  # Single test file
pytest -k "test_name"    # Run tests matching pattern

# API docs: http://localhost:8001/docs (Swagger UI)
```

### Initial Setup

```bash
# Backend
cd backend && conda env create -f environment.yml && conda activate paper-cad

# Frontend
cd frontend && npm install
```

## Architecture

### Frontend (`/frontend/packages/`)

| Package | Purpose |
|---------|---------|
| `chili-web` | Entry point (`src/index.ts`) |
| `chili` | Main application |
| `chili-core` | Document, Model, Material, Selection |
| `chili-ui` | Web Components + CSS Modules |
| `chili-three` | Three.js 3D rendering |
| `chili-cesium` | Cesium 3D Tiles for PLATEAU building picker |
| `chili-wasm` | WebAssembly bindings |

**Build**: Rspack (`rspack.config.js`), env vars in `.env.development`/`.env.demo`

**C++ Kernel** (`/frontend/cpp/src`): OpenCASCADE operations compiled to WebAssembly

### Backend (`/backend`)

**Core Pipeline** (`core/`):
- `file_loaders.py` → `geometry_analyzer.py` → `unfold_engine.py` → `layout_manager.py` → `svg_exporter.py`/`pdf_exporter.py`

**API Routes** (`api/routers/`):
- `step.py`: `POST /api/step/unfold`, `POST /api/step/unfold-pdf`
- `citygml.py`: `POST /api/citygml/to-step`
- `plateau.py`: `POST /api/plateau/search-by-address`

**CityGML Service** (`services/citygml/`): Modular 27-module architecture across 7 layers:
- `core/` → `utils/` → `parsers/` → `geometry/` → `transforms/` → `lod/` → `pipeline/`
- Entry point: `pipeline/orchestrator.py::export_step_from_citygml()`

**Critical CityGML Execution Order**:
1. **PHASE:0** Coordinate recentering (`transforms/recentering.py`) - prevents precision loss
2. **PHASE:1** XLink index building (`utils/xlink_resolver.py`) - required before geometry extraction
3. **PHASE:2-6** LOD extraction → geometry build → validation
4. **PHASE:7** STEP export

### Key Patterns

1. **OpenCASCADE everywhere**: Frontend (WebAssembly) + Backend (pythonOCC)
2. **LOD fallback**: LOD3 → LOD2 → LOD1 priority for maximum detail
3. **Conversion methods**: `solid` (default), `sew`, `extrude`, `auto` (fallback chain)

## Configuration

| Variable | Location | Purpose |
|----------|----------|---------|
| `STEP_UNFOLD_API_URL` | Frontend `.env.*` | Backend API URL |
| `CORS_ALLOW_ALL=true` | Backend env | Enable all CORS (dev only) |
| `FRONTEND_URL` | Backend `.env.*` | CORS allowed origin |

## Common Tasks

**Modifying unfold algorithm**: Edit `backend/core/unfold_engine.py`, test via Swagger UI

**Adding UI component**: Create in `frontend/packages/chili-ui/src/`, use CSS modules

**Modifying 3D ops**: WebAssembly (`frontend/cpp/`) for client-side, backend for server-side

**PLATEAU/Cesium work**:
- Backend: `services/plateau_fetcher.py`, `services/citygml/`
- Frontend: `packages/chili-cesium/src/cesiumBuildingPicker.ts`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Cannot connect to backend | Check backend running on 8001, verify `STEP_UNFOLD_API_URL` |
| Module not found | Run `npm install` from `/frontend` (workspace root) |
| OpenCASCADE 503 | Activate conda: `conda activate paper-cad` |
| CORS errors | Set `CORS_ALLOW_ALL=true` or add frontend URL to `config.py` |
| WASM build fails | Run `npm run setup:wasm` first |

## Deployment

- **Frontend**: Cloudflare Pages (`npm run deploy`)
- **Backend**: Docker/Podman (`docker compose up -d`)
- **Production**: `https://paper-cad.soynyuu.com` (frontend), `https://backend-paper-cad.soynyuu.com` (backend)
