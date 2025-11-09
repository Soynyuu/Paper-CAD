# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paper-CAD is a web-based CAD tool for creating 3D building models and automatically converting them to 2D papercraft templates (展開図/unfold diagrams). The system consists of:

- **Frontend**: TypeScript web application with custom Web Components, Three.js 3D rendering, and WebAssembly CAD kernel
- **Backend**: FastAPI service (Python) with OpenCASCADE Technology for STEP file processing and unfolding algorithms

## Development Commands

### Frontend (from `/frontend`)

```bash
# Development server (port 8080)
npm run dev

# Production build
npm run build

# Demo mode (production performance on localhost, port 8080)
npm run demo          # Build and serve optimized build locally
npm run demo:build    # Build only (for demo mode)

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

# Demo mode (production performance on localhost)
ENV=demo python main.py    # Production settings + localhost CORS

# Tests
# Backend testing is currently done manually via API endpoints
# Use Swagger UI for interactive API testing: http://localhost:8001/docs

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
python main.py  # Starts on http://localhost:8001
```

**Frontend (Node.js 18+):**
```bash
cd frontend
npm install
npm run dev  # Starts on http://localhost:8080
```

**Development Workflow:**
- Frontend (port 8080) communicates with backend (port 8001) via REST API
- Backend API base URL is configured in `rspack.config.js` via `STEP_UNFOLD_API_URL` environment variable
- For local development, backend must be running before testing unfold functionality in frontend
- Frontend has git pre-commit hooks (via `simple-git-hooks` + `lint-staged`) that automatically format code on commit

### Demo Mode

**Demo mode** provides production-like performance on localhost for demos and presentations. It combines:
- ✅ Production optimizations (minification, tree-shaking, multiple workers)
- ✅ Localhost compatibility (same ports as development: 8080 frontend, 8001 backend)
- ✅ No hot-reload overhead (faster than development mode)

**Usage:**

1. **Start backend in demo mode** (in a separate terminal):
```bash
cd backend
conda activate paper-cad
ENV=demo python main.py
```

2. **Start frontend in demo mode**:
```bash
cd frontend
npm run demo
```

3. **Access the application**: Open http://localhost:8080

**Configuration Files:**
- Frontend: `frontend/.env.demo` (points to `http://localhost:8001/api`)
- Backend: `backend/.env.demo` (ENV=demo, production settings + localhost CORS)

**Performance Characteristics:**
- Frontend: Production build (minified, optimized) served via static server
- Backend: No auto-reload, multiple workers (default: 2), production-level settings
- Same speed as production deployment but running locally

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
  - `pdf_exporter.py`: PDF export functionality (uses CairoSVG for SVG→PDF conversion)
  - `step_exporter.py`: Exports back to STEP format
  - `brep_exporter.py`: Exports to BREP format

- **`api/`**: FastAPI routes
  - `endpoints.py`: REST API endpoints
    - `POST /api/step/unfold`: STEP → SVG unfolding (single-page or multi-page layout)
    - `POST /api/step/unfold-pdf`: STEP → PDF export (multi-page papercraft templates)
    - `POST /api/citygml/to-step`: CityGML → STEP conversion
    - `POST /api/citygml/validate`: CityGML validation
    - `POST /api/plateau/search-by-address`: PLATEAU building search by address
    - `POST /api/plateau/fetch-and-convert`: One-step PLATEAU fetch & convert
    - `GET /api/health`: Health check

- **`services/`**: Business logic
  - `step_processor.py`: Orchestrates the unfolding pipeline (calls core modules)
  - `citygml_to_step.py`: CityGML → STEP conversion with LOD2/LOD3 support
  - `plateau_fetcher.py`: PLATEAU Data Catalog API integration (geocoding, building search)
  - `coordinate_utils.py`: Coordinate transformation utilities (CRS conversion)

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
   - `svg_exporter.py`: Generate SVG output (or `pdf_exporter.py` for PDF)
3. Return SVG/PDF file or JSON response

### Key Architectural Patterns

1. **Frontend uses custom Web Components**: Look for classes extending base component classes in `chili-ui/src/`
2. **Backend pipeline is modular**: Each core module handles one concern (load → analyze → unfold → layout → export)
3. **OpenCASCADE is central**: Both frontend (via WebAssembly) and backend (via pythonOCC) use OpenCASCADE Technology
4. **Environment-based configuration**: Frontend uses `__APP_CONFIG__` defined in rspack.config.js; backend uses `.env.development`/`.env.production`

### PLATEAU Integration

The backend includes comprehensive support for Japan's PLATEAU 3D city data:

**Key Features:**
- **Automatic building search**: Search by address or facility name (e.g., "東京駅", "渋谷スクランブルスクエア")
- **Geocoding**: Uses OpenStreetMap Nominatim API to convert addresses to coordinates
- **CityGML processing**: Full LOD2/LOD3 support with XLink reference resolution
- **Building filtering**: Extract specific buildings by ID from large CityGML files
- **Coordinate transformation**: Automatic reprojection from geographic to planar coordinate systems

**API Workflow:**
1. `POST /api/plateau/search-by-address`: Search buildings by address → returns building list with IDs
2. `POST /api/plateau/fetch-and-convert`: One-step fetch & convert (address → STEP file)
3. `POST /api/citygml/to-step`: Convert CityGML to STEP with precision control

**Precision Control** (CityGML → STEP conversion):
- `precision_mode`: Controls tolerance calculation (standard/high/maximum/ultra)
- `shape_fix_level`: Controls geometry repair aggressiveness (minimal/standard/aggressive/ultra)
- `building_ids`: Filter specific buildings from large datasets
- `filter_attribute`: Match by `gml:id` or generic attributes like `buildingID`

**Dependencies:**
- `geopy`: Geocoding (address → coordinates)
- `requests`: HTTP client for PLATEAU API
- `pyproj`: Coordinate system transformations
- `shapely`: Geometry operations

## Important Notes

- **OpenCASCADE dependency**: Backend requires OpenCASCADE (installed via conda). If OCCT is unavailable, API returns 503 for STEP operations.
- **Workspace structure**: Frontend uses npm workspaces. Always run `npm install` from the root `/frontend` directory.
- **API URL configuration**: Update `STEP_UNFOLD_API_URL` in frontend/.env files or rspack.config.js to point to your backend instance.
- **Environment variables**:
  - Frontend: Uses `.env.development`, `.env.demo`, `.env.production.example` (loaded by rspack.config.js)
  - Backend: Uses `.env.development`, `.env.demo`, `.env.production` (loaded by config.py via python-dotenv)
  - Key variables: `STEP_UNFOLD_API_URL` (frontend), `CORS_ALLOW_ALL` (backend development), `FRONTEND_URL` (backend CORS), `PORT` (backend)
- **CORS configuration**: Backend allows configured origins (see `config.py`). Set `CORS_ALLOW_ALL=true` for development.
- **Git branch**: Main branch is `main`. Use `git branch` or `git log` to see the current branch.
- **PDF export dependencies**: Backend uses `cairosvg` (primary) and `reportlab`/`pypdf` (fallback) for PDF generation.

## Troubleshooting

**Frontend issues:**
- **"Cannot connect to backend"**: Ensure backend is running on port 8001. Check `STEP_UNFOLD_API_URL` in `rspack.config.js` or `.env.development` (defaults to `http://localhost:8001/api`)
- **"Module not found" errors**: Run `npm install` from the `/frontend` directory (workspace root), not from individual package directories
- **WebAssembly build fails**: Ensure CMake and Emscripten are installed. Run `npm run setup:wasm` first, then `npm run build:wasm`
- **SVG-Edit icons not displaying**: Check that `node_modules/svgedit/dist/editor` assets are copied to `dist/assets/svgedit` by CopyRspackPlugin

**Backend issues:**
- **"OpenCASCADE not available" / 503 errors**: Activate conda environment with `conda activate paper-cad`. Verify OCCT installation with `python -c "from OCC.Core.BRep import BRep_Builder; print('OK')"`
- **CORS errors in browser console**: Set `CORS_ALLOW_ALL=true` environment variable or add your frontend URL to `config.py` origins list
- **CityGML conversion fails**: Check that `geopy`, `pyproj`, and `shapely` are installed (via conda environment.yml). For specific buildings, verify building IDs using `/api/citygml/validate` endpoint first
- **Frontend test failures**: Run `npm install` from `/frontend` directory and ensure all workspace dependencies are installed

## Testing

**Frontend:**
- Uses Jest with jsdom environment for unit tests
- Test files located in `packages/*/test/*.test.ts`
- Run with `npm test` (from `/frontend` directory)
- Coverage report: `npm run testc`
- Example test files: `observer.test.ts`, `linkedList.test.ts`, `converter.test.ts`, etc.

**Backend:**
- Manual testing via Swagger UI: http://localhost:8001/docs
- Interactive API documentation with request/response examples
- Test endpoints individually with different parameters
- ReDoc alternative: http://localhost:8001/redoc

## Deployment

- **Frontend**: Cloudflare Pages (npm run deploy)
- **Backend**: Docker/Podman containers with conda environment
- **Production URLs**:
  - Frontend: `https://paper-cad.soynyuu.com` or `https://app-paper-cad.soynyuu.com`
  - Backend: `https://backend-paper-cad.soynyuu.com`

## Common Development Patterns

When modifying the unfolding algorithm:
1. Update logic in `backend/core/unfold_engine.py`
2. Test manually via Swagger UI (http://localhost:8001/docs) using the `/api/step/unfold` or `/api/step/unfold-pdf` endpoints
3. Verify with real STEP files and different parameters (scale_factor, page_format, layout_mode)
4. For PDF/SVG export changes: Verify scale_factor propagation through the pipeline (unfold_engine.py → layout_manager.py → svg_exporter.py/pdf_exporter.py)

When adding UI features:
1. Create component in `frontend/packages/chili-ui/src/`
2. Use CSS modules (*.module.css) for styling
3. Wire up to main window via `chili-ui/src/mainWindow.ts` or relevant panel

When modifying 3D operations:
1. Check if operation belongs in WebAssembly (`frontend/cpp/src/`) or backend
2. WebAssembly is for client-side modeling; backend is for server-side STEP processing
3. Remember to rebuild WASM with `npm run build:wasm` if changing C++ code

When working with PLATEAU/CityGML features:
1. Test with real PLATEAU data via Swagger UI endpoints: `/api/plateau/search-by-address`, `/api/plateau/fetch-and-convert`, `/api/citygml/to-step`
2. Key files: `services/plateau_fetcher.py` (API integration), `services/citygml_to_step.py` (conversion logic)
3. Coordinate system handling is in `services/coordinate_utils.py`
4. Building ID filtering logic is in `citygml_to_step.py` (see `extract_buildings_from_citygml` function)
5. For XLink reference resolution, see the `resolve_xlink_references` function in `citygml_to_step.py`
6. **LOD (Level of Detail) Support**: The `_extract_single_solid()` function in `citygml_to_step.py` implements a comprehensive LOD extraction hierarchy with priority-based fallback:

   **LOD3 (Highest Detail - Architectural Models):**
   - Strategy 1: `bldg:lod3Solid//gml:Solid` - Detailed solid structure with architectural elements
   - Strategy 2: `bldg:lod3MultiSurface` - Multiple independent detailed surfaces
   - Strategy 3: `bldg:lod3Geometry` - Generic geometry container for LOD3
   - Strategy 4: `bldg:boundedBy` surfaces - Falls back to boundary surfaces if solids unavailable
   - **LOD3 Features**: Includes detailed walls/roofs, openings (windows/doors), and BuildingInstallation elements

   **LOD2 (PLATEAU's Primary Use Case - Differentiated Roof Structures):**
   - Strategy 1: `bldg:lod2Solid//gml:Solid` - Standard solid structure with roof differentiation
   - Strategy 2: `bldg:lod2MultiSurface` - Multiple independent surfaces
   - Strategy 3: `bldg:lod2Geometry` - Generic geometry container for LOD2
   - Strategy 4: `bldg:boundedBy` surfaces - **Multiple fallback methods** for maximum robustness:
     * First tries LOD-specific wrappers (`lod2MultiSurface`, `lod2Geometry`)
     * Falls back to direct `gml:MultiSurface` or `gml:CompositeSurface` children
     * Final fallback to direct `gml:Polygon` elements
     * This ensures walls/roofs are extracted even when PLATEAU data uses different structural patterns

   **LOD1 (Simple Block Models):**
   - Strategy 1: `bldg:lod1Solid//gml:Solid` - Simple extruded footprint

   **LOD0 (2D Footprints):**
   - Supported via `bldg:lod0FootPrint` and `bldg:lod0RoofEdge` (not used for solid extraction)

   **BoundarySurface Types** (all 6 CityGML 2.0 types supported):
   - `WallSurface`: Vertical exterior walls
   - `RoofSurface`: Roof structures
   - `GroundSurface`: Ground contact surfaces
   - `OuterCeilingSurface`: Exterior ceiling (not a roof)
   - `OuterFloorSurface`: Exterior upper floor (not a roof)
   - `ClosureSurface`: Virtual surfaces to close building volumes

   The fallback chain ensures maximum compatibility with various PLATEAU dataset structures while prioritizing higher detail levels when available.
