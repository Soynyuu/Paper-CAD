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

# Tests (26+ test files available)
# Run specific tests:
python test_polygon_overlap.py      # Polygon overlap detection
python test_improved_unfold.py       # Core unfolding algorithm
python test_adjacency_fix.py         # Edge adjacency detection
python test_brep_export.py           # BREP export functionality
python test_citygml_to_step.py       # CityGML → STEP conversion
python test_plateau_api.py           # PLATEAU API integration
python test_nominatim.py             # Geocoding service
bash test_layout_modes.sh            # Layout mode comparison
bash test_face_numbers.sh            # Face numbering verification

# Pattern: test_*.py for unit/integration tests, test_*.sh for multi-step workflows

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
  - Frontend: Uses `.env.development` and `.env.production` (loaded by rspack.config.js)
  - Backend: No `.env` files in repo (configuration via `config.py` or environment variables)
  - Key variables: `STEP_UNFOLD_API_URL` (frontend), `CORS_ALLOW_ALL` (backend development)
- **CORS configuration**: Backend allows configured origins (see `config.py`). Set `CORS_ALLOW_ALL=true` for development.
- **Git branch**: Main branch is `main`. Use `git branch` or `git log` to see the current branch.
- **PDF export dependencies**: Backend uses `cairosvg` (primary) and `reportlab`/`pypdf` (fallback) for PDF generation.

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
1. Test with real PLATEAU data using `test_plateau_api.py` or `test_citygml_to_step.py`
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
