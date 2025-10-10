# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paper-CAD is a web-based CAD tool for creating 3D building models and automatically converting them to 2D papercraft templates (展開図/unfold diagrams). The system consists of:

- **Frontend**: TypeScript web application with custom Web Components, Three.js 3D rendering, and WebAssembly CAD kernel
- **Backend**: FastAPI service (Python) with OpenCASCADE Technology for STEP file processing and unfolding algorithms

## Development Commands

### Frontend (from `/frontend`)

```bash
# Development server (port 3001)
npm run dev

# Production build
npm run build

# Build WebAssembly (C++)
npm run build:wasm

# Tests
npm test              # Run tests
npm run testc         # Run tests with coverage

# Code formatting
npm run format        # Formats TypeScript/JS and C++ files

# Deployment (Cloudflare Pages)
npm run deploy               # Deploy to Cloudflare
npm run deploy:staging       # Deploy to staging branch
npm run deploy:production    # Deploy to production
```

### Backend (from `/backend`)

```bash
# Development server (requires Conda environment)
conda activate paper-cad
python main.py        # Starts server on http://localhost:8001

# Tests
python test_polygon_overlap.py
bash test_layout_modes.sh
python test_brep_export.py

# Docker/Podman
docker compose up -d
bash podman-deploy.sh build-run

# API documentation (once running)
# Swagger UI: http://localhost:8001/docs
# ReDoc: http://localhost:8001/redoc
```

### Initial Setup

**Backend (Python 3.10+):**
```bash
cd backend
conda env create -f environment.yml
conda activate paper-cad
python main.py
```

**Frontend (Node.js 18+):**
```bash
cd frontend
npm install
npm run dev
```

## Architecture

### Frontend Structure (`/frontend`)

**Monorepo with workspace packages** under `packages/`:

- `chili`: Main application package
- `chili-core`: Core data structures (Document, Application, Model, Material, Navigation, Selection)
- `chili-ui`: UI components (web components with CSS modules)
- `chili-three`: Three.js integration for 3D rendering
- `chili-wasm`: WebAssembly bindings for C++ CAD kernel
- `chili-web`: Entry point and main window
- `chili-builder`, `chili-controls`, `chili-geo`, `chili-vis`, `chili-storage`: Supporting utilities

**Build Configuration:**
- Entry point: `packages/chili-web/src/index.ts`
- Build tool: Rspack (rspack.config.js)
- The frontend communicates with backend via environment variable `STEP_UNFOLD_API_URL` (default: `https://backend-paper-cad.soynyuu.com/api`)

**C++ WebAssembly Kernel** (`/frontend/cpp/src`):
- OpenCASCADE-based CAD operations compiled to WebAssembly
- Key files: `opencascade.cpp`, `converter.cpp`, `factory.cpp`, `shape.cpp`, `mesher.cpp`, `geometry.cpp`

### Backend Structure (`/backend`)

**Clear separation of concerns:**

- **`core/`**: Core processing pipeline
  - `file_loaders.py`: STEP/BREP file I/O
  - `geometry_analyzer.py`: Analyzes geometry properties (planarity, adjacency)
  - `unfold_engine.py`: Main unfolding algorithm (展開エンジン) - converts 3D faces to 2D polygons
  - `layout_manager.py`: Arranges unfolded pieces on canvas or pages (A4/A3/Letter)
  - `svg_exporter.py`: Exports to SVG with fold/cut lines and assembly tabs
  - `step_exporter.py`: Exports back to STEP format
  - `brep_exporter.py`: Exports to BREP format

- **`api/`**: FastAPI routes
  - `endpoints.py`: REST API endpoints (`POST /api/step/unfold`, `GET /api/health`)

- **`services/`**: Business logic
  - `step_processor.py`: Orchestrates the unfolding pipeline (calls core modules)
  - `citygml_to_step.py`: Experimental CityGML → STEP conversion
  - `coordinate_utils.py`: Coordinate transformation utilities

- **`models/`**: Pydantic models for API requests/responses
- **`utils/`**: Shared utilities
- **`config.py`**: App configuration, CORS setup, OCCT availability check
- **`main.py`**: FastAPI app entry point with uvicorn server

**Key Backend Flow:**
1. API receives STEP file → `endpoints.py`
2. `step_processor.py` orchestrates:
   - `file_loaders.py`: Load STEP → shape
   - `geometry_analyzer.py`: Analyze faces, edges, adjacency
   - `unfold_engine.py`: Unfold 3D → 2D with tabs
   - `layout_manager.py`: Arrange on canvas/pages
   - `svg_exporter.py`: Generate SVG output
3. Return SVG or JSON response

### Key Architectural Patterns

1. **Frontend uses custom Web Components**: Look for classes extending base component classes in `chili-ui/src/`
2. **Backend pipeline is modular**: Each core module handles one concern (load → analyze → unfold → layout → export)
3. **OpenCASCADE is central**: Both frontend (via WebAssembly) and backend (via pythonOCC) use OpenCASCADE Technology
4. **Environment-based configuration**: Frontend uses `__APP_CONFIG__` defined in rspack.config.js; backend uses `.env.development`/`.env.production`

## Important Notes

- **OpenCASCADE dependency**: Backend requires OpenCASCADE (installed via conda). If OCCT is unavailable, API returns 503 for STEP operations.
- **Workspace structure**: Frontend uses npm workspaces. Always run `npm install` from the root `/frontend` directory.
- **API URL configuration**: Update `STEP_UNFOLD_API_URL` in frontend/.env files or rspack.config.js to point to your backend instance.
- **CORS configuration**: Backend allows configured origins (see `config.py`). Set `CORS_ALLOW_ALL=true` for development.
- **Git branch**: Main branch is `main`. Current feature branch: `feature/assembly-mode`.

## Testing

- Frontend tests use Jest with jsdom environment
- Backend tests are primarily integration tests (test_*.py) and shell scripts (test_*.sh)
- Always run tests after significant changes to unfolding algorithms or UI components

## Deployment

- **Frontend**: Cloudflare Pages (npm run deploy)
- **Backend**: Docker/Podman containers with conda environment
- **Production URLs**:
  - Frontend: `https://paper-cad.soynyuu.com`
  - Backend: `https://backend-paper-cad.soynyuu.com`

## Common Development Patterns

When modifying the unfolding algorithm:
1. Update logic in `backend/core/unfold_engine.py`
2. Test with `python test_improved_unfold.py` or `bash test_layout_modes.sh`
3. If changing adjacency detection, run `python test_adjacency_fix.py`

When adding UI features:
1. Create component in `frontend/packages/chili-ui/src/`
2. Use CSS modules (*.module.css) for styling
3. Wire up to main window via `chili-ui/src/mainWindow.ts` or relevant panel

When modifying 3D operations:
1. Check if operation belongs in WebAssembly (`frontend/cpp/src/`) or backend
2. WebAssembly is for client-side modeling; backend is for server-side STEP processing
3. Remember to rebuild WASM with `npm run build:wasm` if changing C++ code
- 作業を始める際は、github issueにやることを書いて、ブランチを切って作業するようにして