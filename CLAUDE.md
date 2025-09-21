# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two integrated projects developed for the 2025 Mitou Junior Program, collectively called Paper-CAD:

1. **chili3d** - Browser-based 3D CAD application (fork of [xiangechen/chili3d](https://github.com/xiangechen/chili3d))
2. **unfold-step2svg** - 3D-to-2D papercraft generation service

Both projects integrate to provide a complete 3D modeling to physical papercraft workflow.

## Common Development Commands

### chili3d (TypeScript/WebAssembly CAD)

```bash
cd chili3d
npm install                 # First-time setup
npm run dev                # Dev server at http://localhost:8080
npm run build             # Production build
npm run build:wasm        # Rebuild WASM (requires cmake)
npm test                  # Run all tests
npm test -- packages/chili-core/test/math.test.ts  # Single test
npm run format            # Format TS and C++ code
npx tsc --noEmit         # Type check
```

### unfold-step2svg (Python/FastAPI Service)

```bash
cd unfold-step2svg
conda env create -f environment.yml    # First-time setup
conda activate unfold-step2svg
python main.py                         # API at http://localhost:8001

# API Testing
curl http://localhost:8001/api/health
curl -X POST -F "file=@model.step" http://localhost:8001/api/step/unfold -o output.svg
```

## High-Level Architecture

### chili3d - Monorepo Structure

**Core Design Principles:**
- Interface-based architecture with 11 npm workspace packages
- WebAssembly integration for native-speed OpenCASCADE operations
- Custom reactive UI system with property decorators

**Key Packages:**
- `chili-core`: Interfaces (IDocument, INode, ICommand) - contract definitions
- `chili-wasm`: OpenCASCADE WASM bindings - geometry engine
- `chili-three`: Three.js visualization - 3D rendering
- `chili-ui`: Custom UI framework with ribbon interface
- `chili`: Main application logic - commands, snapping, steps
- `chili-builder`: Application initialization via builder pattern

**Architectural Patterns:**

1. **Builder Pattern Configuration:**
   ```typescript
   new AppBuilder()
     .useIndexedDB()
     .useWasmOcc()
     .useThree()
     .useUI()
     .build();
   ```

2. **Command Pattern with Undo/Redo:**
   - All user actions are commands in `packages/chili/src/commands/`
   - Categories: `create/`, `modify/`, `measure/`, `application/`
   - Multi-step commands via `MultistepCommand`

3. **Step-Based User Interaction:**
   - Complex operations broken into steps (`packages/chili/src/step/`)
   - Steps handle validation, user input, and state transitions

4. **Service Architecture:**
   - Services registered via `AppBuilder.getServices()`
   - Key services: `CommandService`, `HotkeyService`, `StepUnfoldService`
   - `StepUnfoldService` integrates with unfold-step2svg backend

### unfold-step2svg - Pipeline Architecture

**Processing Pipeline:**
1. **File Loading** (`core/file_loaders.py`) - STEP/BREP parsing
2. **Geometry Analysis** (`core/geometry_analyzer.py`) - Face classification
3. **Unfolding** (`core/unfold_engine.py`) - 3D→2D transformation
4. **Layout** (`core/layout_manager.py`) - Canvas or paged layout
5. **Export** (`core/svg_exporter.py`) - SVG with face numbers

**Service Layer:**
- `StepUnfoldGenerator` in `services/step_processor.py` orchestrates the pipeline
- FastAPI endpoints in `api/endpoints.py`

**Key Features:**
- Dual layout modes: dynamic canvas or fixed pages (A4/A3/Letter)
- Face numbering synchronized with chili3d's 3D display
- Debug file generation in `core/debug_files/` for troubleshooting

## Integration Points

### Backend Service Connection
- chili3d's `StepUnfoldService` calls unfold-step2svg at https://backend-diorama.soynyuu.com
- STEP export from chili3d → Processing in unfold-step2svg → SVG import back
- Face numbers synchronized between 3D view and 2D papercraft

### Face Numbering System
- chili3d: 3D face numbers via Three.js sprites (`packages/chili-three/src/faceNumberDisplay.ts`)
- unfold-step2svg: 2D face numbers in SVG (`core/svg_exporter.py`)
- Both use normal vector analysis for consistent numbering

## Critical Implementation Details

### chili3d Specifics
- **WASM Memory Management**: Use `gc()` helper for OpenCASCADE objects
- **Document Version**: 0.6 - increment when changing serialization
- **Reactive UI**: Custom decorators for data binding in `.module.css` files
- **Build Tool**: Rspack (faster than Webpack)
- **Testing**: Jest with ESM support, CSS modules mocked

### unfold-step2svg Specifics
- **OpenCASCADE Version**: 7.9.0 via pythonocc-core
- **Max Faces**: Limited to 20 faces per model for performance
- **Scale Factor**: Default 10.0 for mm to SVG units
- **Error Recovery**: Failed operations save debug STEP files

## Working with WASM (chili3d)

```javascript
// Always await initialization
await initWasm();

// Memory management pattern
const shape = createShape();
try {
  // Use shape
} finally {
  gc(shape);  // Manual cleanup
}
```

## API Endpoints (unfold-step2svg)

```bash
POST /api/step/unfold
  file: STEP file (required)
  return_face_numbers: bool (default: true)
  layout_mode: "canvas" | "paged"
  page_format: "A4" | "A3" | "Letter"
  scale_factor: float (default: 10.0)
```

## Testing Strategies

### chili3d
```bash
npm test                     # All tests
npm test -- --watch         # Watch mode
npm test -- path/to/test.ts # Specific test
```

### unfold-step2svg
```bash
bash test_face_numbers.sh    # Face numbering
bash test_layout_modes.sh    # Layout modes
python test_*.py            # Python unit tests
```

## Key File Locations

### chili3d Configuration
- `rspack.config.js` - Build configuration
- `packages/*/src/` - Package source code
- `cpp/src/` - C++ OpenCASCADE bindings

### unfold-step2svg Configuration
- `environment.yml` - Conda dependencies
- `core/` - Processing pipeline modules
- `api/config.py` - Server configuration

## License Notes
- chili3d: AGPL-3.0 (inherited from fork, commercial licensing available)
- unfold-step2svg: MIT License