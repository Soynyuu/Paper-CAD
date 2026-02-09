# Repository Guidelines for AI Agents

## Project Overview
Paper-CAD is a CAD application for unfolding 3D models into 2D SVG/PDF patterns. The frontend is a TypeScript monorepo (Rspack), the backend is a FastAPI Python server with OpenCASCADE for geometry processing. A C++ kernel (OpenCASCADE) compiles to WebAssembly.

## Project Structure
```
Paper-CAD/
├── frontend/                  # TypeScript monorepo (Rspack + npm workspaces)
│   ├── packages/
│   │   ├── chili-web/         # Entry point (src/index.ts)
│   │   ├── chili/             # Main application
│   │   ├── chili-core/        # Document, Model, Material, Selection
│   │   ├── chili-ui/          # Web Components + CSS Modules
│   │   ├── chili-three/       # Three.js integration
│   │   ├── chili-cesium/      # Cesium 3D Tiles for PLATEAU
│   │   ├── chili-wasm/        # WebAssembly bindings
│   │   └── chili-*/           # Other feature modules
│   ├── cpp/                   # C++ OpenCASCADE → WASM
│   └── test files in packages/*/test/
├── backend/
│   ├── api/                   # REST API routing
│   ├── core/                  # Unfold pipeline (file_loaders, geometry_analyzer, etc.)
│   ├── services/              # External integrations (citygml/, plateau_fetcher, etc.)
│   ├── models/                # Pydantic models
│   ├── tests/                 # pytest tests
│   └── main.py                # FastAPI entry
├── lp/                        # Landing page (Vite + React + Tailwind)
└── docs/                      # Documentation
```

## Build, Test, and Development Commands

### Frontend (from `/frontend`)
```bash
npm install                 # Install dependencies
npm run dev                 # Dev server http://localhost:8080
npm run build               # Production build
npm run build:wasm          # Build C++ WASM kernel
npm test                    # Run all Jest tests
npm run format              # Prettier + clang-format
```

**Run a single test:**
```bash
npm test -- packages/chili-core/test/observer.test.ts
npm test -- --testPathPattern="math"       # Pattern matching
```

### Backend (from `/backend`)
```bash
conda env create -f environment.yml
conda activate paper-cad
python main.py              # API http://localhost:8001
ENV=demo python main.py     # Demo mode
pytest                      # Run all tests
```

**Run a single test:**
```bash
pytest tests/citygml/streaming/test_parser.py -v
pytest -k "test_function_name"             # Pattern matching
pytest tests/test_mesh2_mapping.py::test_specific -v
```

## TypeScript Code Style

### Formatting
- **Prettier**: tabWidth 4, printWidth 109
- Pre-commit hook auto-formats `*.{ts,js,css,json,md}`
- Run `npm run format` to format all files

### Imports
```typescript
// Use barrel exports (re-export from index.ts)
export * from "./module";

// Import from package root, not deep paths
import { Material, Document } from "chili-core";  // Good
import { Material } from "chili-core/src/material";  // Avoid

// Relative imports within package
import { DeepObserver, Observable } from "../src";
```

### Types and Interfaces
- Use `interface` for object shapes, `type` for unions/aliases
- Prefix interfaces with `I` for contracts: `IDocument`, `IPropertyChanged`
- Use strict TypeScript (`"strict": true` in tsconfig)
- Always type function parameters and return values

### Naming Conventions
- **Packages**: `chili-*` (kebab-case)
- **Components/Classes**: PascalCase (`Material`, `Document`)
- **Variables/Functions**: camelCase (`getDocument`, `unfoldFaces`)
- **Constants**: UPPER_SNAKE_CASE for true constants
- **Files**: camelCase.ts or PascalCase.ts for classes

### Class Patterns
```typescript
// Use decorators for serialization and properties
@Serializer.register(["document", "name", "color", "id"])
export class Material extends HistoryObservable {
    @Serializer.serialze()
    @Property.define("common.name")
    get name(): string {
        return this.getPrivateValue("name", "");
    }
    set name(value: string) {
        this.setProperty("name", value);
    }
}
```

## Python Code Style

### Formatting & Imports
- **Indentation**: 4 spaces (PEP8)
- Use type hints consistently
```python
# Standard library → Third-party → Local
import math
from typing import List, Dict, Optional
import numpy as np
from config import OCCT_AVAILABLE
```

### Naming Conventions
- **Classes**: PascalCase (`UnfoldEngine`, `StreamingConfig`)
- **Functions/Variables**: snake_case (`group_faces_for_unfolding`)
- **Constants**: UPPER_SNAKE_CASE (`OCCT_AVAILABLE`)
- **Private**: prefix with underscore (`_internal_method`)

## Testing Guidelines

### Frontend Tests (Jest)
- Location: `frontend/packages/*/test/*.test.ts(x)`
```typescript
test("deep observer tracks nested property changes", () => {
    const c = new TestClassC();
    c.propC!.propB = new TestClassA();
    expect(targetProperty).toBe("propC.propB");
});
```

### Backend Tests (pytest)
- Location: `backend/tests/test_*.py`
```python
@pytest.fixture
def sample_citygml_single_building():
    """Create a minimal CityGML file with one building."""
    # ...

def test_streaming_parser_limits_buildings(sample_citygml_single_building):
    # Test implementation
```

### When to Add Tests
- Geometry/math changes require regression tests
- PLATEAU/CityGML integration changes need tests
- Any SVG/PDF output changes should be tested

## Commit & PR Guidelines
- Use prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Write imperative summary: "Add face grouping" not "Added face grouping"
- Avoid `wip` commits
- PR must include: summary, background, test results
- UI/SVG changes: include screenshots or GIFs
- Link related Issues

## Environment Variables

### Frontend (`.env.*`)
| Variable | Required | Description |
|----------|----------|-------------|
| `STEP_UNFOLD_API_URL` | No | Backend API URL (default: `http://localhost:8001/api`) |
| `STEP_UNFOLD_WS_URL` | No | Reserved for future WebSocket use (currently unused) |

### Backend (`.env.*`)
| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | No | Server port (default: 8001) |
| `FRONTEND_URL` | No | CORS origin |
| `CORS_ALLOW_ALL` | No | Allow all CORS |

## Prerequisites
- Node.js 18+
- Python 3.10 (Conda recommended)
- OpenCASCADE (via conda-forge) for STEP processing
