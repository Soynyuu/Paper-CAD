# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A 3D-to-2D papercraft generation system that converts STEP CAD files into unfolded SVG diagrams. Part of the 2025 Mitou Junior program, using OpenCASCADE Technology for 3D geometry processing.

Repository: https://github.com/Soynyuu/unfold-step2svg

## Development Commands

```bash
# Environment setup
conda env create -f environment.yml
conda activate unfold-step2svg

# Run server
python main.py  # Starts on localhost:8001

# Test endpoints
curl http://localhost:8001/api/health

# Test STEP to SVG conversion
curl -X POST \
  -F "file=@model.step" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg

# Test scripts
bash test_face_numbers.sh     # Test face numbering feature
bash test_layout_modes.sh     # Test different layout modes
python test_brep_export.py    # Test BREP export methods
python test_face_numbering.py # Test face numbering functionality
python test_polygon_overlap.py # Test polygon intersection detection
```

## Architecture

**Core Processing Pipeline:**
1. **File Loading** (`core/file_loaders.py`) - STEP/BREP parsing using OpenCASCADE
2. **Geometry Analysis** (`core/geometry_analyzer.py`) - Face classification (planar, cylindrical, conical)
3. **Unfolding** (`core/unfold_engine.py`) - 3D to 2D transformation algorithms
4. **Layout** (`core/layout_manager.py`) - Page optimization with two modes:
   - Canvas mode: Dynamic canvas size
   - Paged mode: Fixed page sizes (A4, A3, Letter)
5. **Export** (`core/svg_exporter.py`) - SVG generation with face numbering

**Service Layer:**
- `services/step_processor.py` - Main orchestrator class `StepUnfoldGenerator` that coordinates the pipeline

**Support Modules:**
- `core/brep_exporter.py` - BREP format export functionality
- `core/step_exporter.py` - STEP format export functionality

## API Endpoints

```bash
POST /api/step/unfold
  # Required:
  - file: STEP file (.step or .stp)
  
  # Optional parameters:
  - return_face_numbers: bool (default: True)
  - output_format: "svg" | "json" (default: "svg")
  - layout_mode: "canvas" | "paged" (default: "canvas")
  - page_format: "A4" | "A3" | "Letter" (default: "A4")
  - page_orientation: "portrait" | "landscape" (default: "portrait")
  - scale_factor: float (default: 10.0)

GET /api/health
  # Returns system status and OpenCASCADE availability
```

## Request Models

The `models/request_models.py` defines `BrepPapercraftRequest` with key parameters:
- `scale_factor`: Default 10.0
- `max_faces`: Maximum 20 faces to process
- `tab_width`: 5.0mm for assembly tabs
- `min_face_area`: 1.0 to filter tiny faces
- `layout_mode`: "canvas" or "paged"
- `page_format`: A4, A3, Letter
- `page_orientation`: portrait or landscape

## Key Dependencies

- **OpenCASCADE 7.9.0** (`pythonocc-core`) - Industrial CAD kernel, required for all operations
- **FastAPI** - Web framework
- **svgwrite** - SVG generation
- **scipy/numpy** - Scientific computing for geometry operations
- **networkx** - Graph algorithms for face connectivity
- **shapely** - Polygon intersection detection

## Error Handling

- Failed operations save debug files to `core/debug_files/`
- OpenCASCADE availability checked at startup
- Detailed error messages for geometry processing failures

## Layout System

Two distinct layout modes:
1. **Canvas mode**: Dynamic canvas that adjusts to content size
2. **Paged mode**: Fixed page sizes with automatic pagination
   - Supports A4 (210×297mm), A3 (297×420mm), Letter (216×279mm)
   - Automatic page breaks and margin handling
   - Returns ZIP file when multiple pages needed

## Face Numbering

- Generated server-side based on normal vectors
- Dynamically sized according to face area
- Numbers placed at face centroids
- Implementation in `core/svg_exporter.py`

## Debug Files

The system automatically saves debug STEP files in `core/debug_files/` when processing fails. These files use timestamp-based naming: `debug_YYYYMMDD-HHMMSS_<tempfile>.step`