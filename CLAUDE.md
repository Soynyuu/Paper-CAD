# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two projects developed for the 2025 Mitou Junior Program:

### 1. chili3d - Web-based 3D CAD Application
- **Location**: `chili3d/`
- **Technology**: TypeScript, Three.js, OpenCascade (WebAssembly)
- **Repository**: https://github.com/Soynyuu/chili3d
- **Description**: Browser-based 3D CAD application with advanced modeling tools, snapping system, and WebAssembly-powered geometry operations

### 2. unfold-step2svg - 3D-to-2D Papercraft System  
- **Location**: `unfold-step2svg/`
- **Technology**: Python, FastAPI, OpenCASCADE (pythonocc-core), ifcopenshell
- **Repository**: https://github.com/Soynyuu/unfold-step2svg
- **Description**: Web service that converts 3D STEP files and CityGML models into 2D papercraft SVG diagrams

## Development Commands

### chili3d (Web CAD Application)
```bash
cd chili3d
npm install
npm run dev                # Start dev server at http://localhost:8080
npm run build             # Production build
npm run build:wasm        # Build WebAssembly module (requires cmake)
npm test                  # Run Jest tests
npm run format            # Format TypeScript and C++ code
npm run setup:wasm        # Setup WASM dependencies
```

### unfold-step2svg (Papercraft Service)
```bash
cd unfold-step2svg
conda env create -f environment.yml
conda activate unfold-step2svg
python main.py            # Start FastAPI server at http://localhost:8001
curl http://localhost:8001/api/health  # Health check
```

## Architecture Overview

### chili3d Architecture
- **Monorepo Structure**: 11 packages using npm workspaces
- **Core Packages**:
  - `chili-core`: Interfaces and abstractions (IDocument, INode, ICommand)
  - `chili-wasm`: OpenCascade WebAssembly bindings
  - `chili-three`: Three.js visualization implementation
  - `chili-ui`: Custom UI framework with ribbon interface
  - `chili`: Main application logic with commands and snapping
  - `chili-web`: Web entry point

- **Key Patterns**:
  - Builder pattern for app configuration (`AppBuilder`)
  - Command pattern with undo/redo support
  - Interface-based service architecture
  - Step-based user interactions
  - Custom reactive UI system

### unfold-step2svg Architecture
- **Modular Pipeline**: STEP → Geometry Analysis → Unfolding → Layout → SVG
- **Dual CityGML Processing**:
  - Modern IFC Pipeline (default): CityGML → IFC → STEP
  - Legacy OpenCASCADE Pipeline: CityGML → Solids → STEP
- **Key Components**:
  - FastAPI web service with comprehensive error handling
  - OpenCASCADE Technology 7.9.0 for 3D geometry processing
  - Multi-page layout optimization (A4, A3, Letter formats)
  - Debug file system for troubleshooting

## Project Integration

Both projects share common themes:
- **OpenCASCADE Technology**: Industrial-grade CAD kernel used in both projects
- **3D Geometry Processing**: Advanced 3D modeling and conversion capabilities  
- **Web-based Architecture**: Modern web technologies for accessibility
- **Japanese/International Focus**: Support for CityGML/Plateau standards and multi-language interfaces

## Development Notes

### chili3d Specific
- Uses Rspack for faster builds than Webpack
- WebAssembly requires async initialization
- Custom reactive UI system with property decorators
- AGPL-3.0 license with commercial licensing available

### unfold-step2svg Specific
- Conda environment management for complex scientific dependencies
- Dual pipeline architecture for CityGML processing reliability
- Automatic debug file generation in `core/debug_files/`
- MIT license

## Testing and Quality

### chili3d
- Jest with ESM support and JSDOM environment
- CSS modules mocked for testing
- Pre-commit hooks with prettier and clang-format
- Test command: `npm test`

### unfold-step2svg
- No established testing framework (should implement pytest)
- Comprehensive error handling and logging
- API validation with Pydantic models
- Health check endpoint for system monitoring

## Common Development Patterns

- **Error Handling**: Both projects use Result patterns and comprehensive error reporting
- **Modular Design**: Clear separation of concerns with well-defined interfaces
- **Performance Focus**: Optimized for handling complex 3D geometry operations
- **Debug Support**: Extensive debugging capabilities and logging systems