# Repository Guidelines for AI Agents

## Project Overview
Paper-CAD is a CAD application for unfolding 3D models into 2D SVG/PDF patterns. The frontend is a TypeScript monorepo (Rspack + npm workspaces), the backend is a FastAPI Python server with OpenCASCADE for geometry processing. A C++ kernel (OpenCASCADE) compiles to WebAssembly.

## Project Structure
- `frontend/` -- TypeScript monorepo (Rspack + npm workspaces)
  - `packages/chili-web/` (entry point), `chili/` (main app), `chili-core/` (Document, Model, Material, Selection), `chili-ui/` (Web Components + CSS Modules), `chili-three/` (Three.js), `chili-cesium/` (Cesium 3D Tiles), `chili-wasm/` (WASM bindings)
  - `cpp/` -- C++ OpenCASCADE -> WASM; tests in `packages/*/test/`
- `backend/` -- FastAPI Python server
  - `api/` (routers), `core/` (unfold pipeline), `services/` (CityGML, PLATEAU), `models/` (Pydantic), `tests/`
- `lp/` -- Landing page (Vite + React + Tailwind)

## Build, Test, and Development Commands

### Frontend (run from `/frontend`)
```bash
npm install                 # Install dependencies
npm run dev                 # Dev server http://localhost:8080
npm run build               # Production build
npm run build:wasm          # Build C++ WASM kernel
npm test                    # Run all Jest tests (uses --experimental-vm-modules)
npm run format              # Prettier + clang-format

# Run a single test file:
npm test -- packages/chili-core/test/observer.test.ts
# Pattern matching:
npm test -- --testPathPattern="math"
```

### Backend (run from `/backend`)
```bash
conda env create -f environment.yml && conda activate paper-cad
python main.py              # API http://localhost:8001
pytest                      # Run all tests

# Run a single test file:
pytest tests/test_layout_manager.py -v
# Run a specific test function:
pytest tests/test_mesh2_mapping.py::test_mesh2_mapping_contains_municipality -v
# Pattern matching:
pytest -k "test_function_name"
```

### Landing Page (run from `/lp`)
```bash
npm install && npm run dev  # Dev server
npm run build               # Production build
```

## TypeScript Code Style

### Formatting
- **Prettier**: tabWidth 4, printWidth 109 (`.prettierrc`)
- **Pre-commit hook** (simple-git-hooks + lint-staged): auto-formats `*.{ts,js,css,json,md}`
- C++ files use clang-format with WebKit style

### Imports
```typescript
// Import from package root via barrel exports (index.ts), not deep paths
import { Material, Document } from "chili-core";     // Good
import { Material } from "chili-core/src/material";   // Avoid
// Relative imports within a package
import { DeepObserver, Observable } from "../src";
```

### Types and Interfaces
- `interface` for object shapes; `type` for unions/aliases
- **`I` prefix** for contract/capability interfaces: `IDocument`, `IService`, `IDisposable`
- **No prefix** for data shape interfaces: `UnfoldOptions`, `UnfoldResponse`
- Companion namespaces with type guards: `IDisposable.isDisposable(value)`
- Strict TypeScript (`"strict": true`, `experimentalDecorators`, `noImplicitOverride`)

### Naming Conventions
- **Packages**: `chili-*` (kebab-case)
- **Classes/Components**: PascalCase (`Material`, `Document`)
- **Variables/Functions**: camelCase (`getDocument`, `unfoldFaces`)
- **Constants**: UPPER_SNAKE_CASE
- **Files**: camelCase.ts or PascalCase.ts for class files

### Decorator Patterns
```typescript
// Class decorator: register for serialization with constructor param names
@Serializer.register(["document", "name", "color", "id"])
export class Material extends HistoryObservable {
    // Property decorator: mark field for serialization
    @Serializer.serialze()
    @Property.define("common.color", { type: "color" })
    get color(): number | string {
        return this.getPrivateValue("color");
    }
    set color(value: number | string) {
        this.setProperty("color", value);
    }
}
```

### Error Handling (Frontend)
- Use `Result<T, E>` monadic type instead of throwing exceptions
- Service methods return `Promise<Result<...>>`, never throw
- Map HTTP status codes to user-facing error messages in service layer
```typescript
// Good: return Result
return Result.err("Invalid STEP file");
return Result.ok(responseData);
// Bad: throw
throw new Error("Invalid STEP file");
```

## Python Code Style

### Formatting & Imports
- **PEP 8**: 4-space indentation
- Import order: standard library -> third-party -> local
- Use type hints consistently (Python 3.10+ union syntax: `str | None`)
```python
import math
from typing import List, Dict, Optional
import numpy as np
from config import OCCT_AVAILABLE
```

### Naming Conventions
- **Classes**: PascalCase (`UnfoldEngine`, `StreamingConfig`)
- **Functions/Variables**: snake_case (`group_faces_for_unfolding`)
- **Constants**: UPPER_SNAKE_CASE (`OCCT_AVAILABLE`)
- **Private**: underscore prefix (`_internal_method`, `_helper_func`)

### Error Handling (Backend)
- **Core layer** (`core/`): raise `ValueError` with descriptive messages
- **API layer** (`api/`): catch `ValueError` -> `HTTPException(400)`, unexpected -> `HTTPException(500)`
- **Graceful import fallbacks**: try/except ImportError with `*_AVAILABLE` boolean flags
```python
# Core: raise domain errors
raise ValueError(f"BREP file read failed: {file_path}")
# API: map to HTTP errors
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"[STEP UNFOLD] Error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
```

### Logging
- Use centralized logger: `from utils.logger import get_logger; logger = get_logger(__name__)`
- Use bracketed prefixes for grep-ability: `logger.info(f"[UPLOAD] received {n} bytes")`
- Environment-aware: DEBUG in development, INFO in production

## Testing Guidelines

### Frontend Tests (Jest, jsdom environment)
- Location: `frontend/packages/*/test/*.test.ts(x)`
- Import from `"../src"` barrel export
- Use `describe()` blocks for grouping, `test()` for individual tests
- `beforeEach()` for setup; `toEqual()` for deep comparison

### Backend Tests (pytest)
- Location: `backend/tests/test_*.py`
- `@pytest.fixture` with `yield` for setup/teardown
- `pytest.approx()` for floating-point comparisons
- `@pytest.mark.parametrize` for data-driven tests
- `pytest.skip()` for conditional skipping (external data dependencies)
- Group related tests in classes: `class TestCacheConfiguration:`

### When to Add Tests
- Geometry/math changes require regression tests
- PLATEAU/CityGML integration changes need tests
- Any SVG/PDF output changes should be tested

## Commit & PR Guidelines
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Write imperative summary: "Add face grouping" not "Added face grouping"
- Branch naming: `feat/feature-name`, `fix/bug-description`, `refactor/target`
- PR must include: summary, related Issue (`Closes #123`), test results
- UI/SVG changes: include screenshots or GIFs
