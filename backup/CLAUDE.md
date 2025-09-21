# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chili3D (formerly Diorama-CAD) is a web-based 3D CAD application built with TypeScript, OpenCascade (WASM), and Three.js. It follows a monorepo structure using npm workspaces with 11 packages.

Repository: https://github.com/Soynyuu/chili3d
Live applications: [chili3d.com](https://chili3d.com) and [chili3d.pages.dev](https://chili3d.pages.dev)

## Common Development Commands

```bash
# Development
npm run dev              # Start dev server at http://localhost:8080
npm run build            # Production build (uses Rspack)
npm run build:wasm       # Build WebAssembly module (requires cmake)

# Testing
npm test                 # Run all tests (Jest with ESM support)
npm run testc           # Run tests with coverage
npm test -- packages/chili-core/test/math.test.ts  # Run specific test

# Code Quality
npm run format          # Format all code (TypeScript + C++ with clang-format)

# Setup
npm install             # Install dependencies
npm run setup:wasm      # Setup WASM dependencies
```

## Architecture Overview

### Monorepo Structure

- **chili-core**: Core interfaces and abstractions (IDocument, INode, ICommand, foundation classes)
- **chili-wasm**: OpenCascade WebAssembly bindings for geometry operations
- **chili-three**: Three.js implementation of visualization interfaces
- **chili-ui**: Custom UI framework with components (editor, ribbon, dialogs, property panels)
- **chili**: Main application with commands, steps, snapping, and business logic
- **chili-web**: Web entry point and AppBuilder initialization
- **chili-builder**: Application builder pattern for service registration
- **chili-controls**: Reusable UI controls and converters
- **chili-storage**: IndexedDB storage implementation
- **chili-vis**: Visual selection and event handling
- **chili-geo**: Geometry utilities and mesh operations

### Key Architectural Patterns

1. **Builder Pattern**: `AppBuilder` in chili-builder configures the application

    ```typescript
    new AppBuilder().useIndexedDB().useWasmOcc().useThree().useUI().build();
    ```

2. **Interface-Based Design**: Core defines interfaces, other packages implement

    - Services: `IShapeFactory`, `IVisualFactory`, `IStorage`, `IDataExchange`
    - Models: `IDocument`, `INode`, `ICommand`

3. **Command Pattern**: All user actions are commands with undo/redo support

    - Commands in `packages/chili/src/commands/` organized by category
    - Multi-step commands supported via `MultistepCommand`

4. **Service Registration**: Services registered via AppBuilder

    - `CommandService`, `HotkeyService`, `EditorService` auto-registered
    - Custom services can be added via `getServices()`

5. **Step-Based Interaction**: Complex operations broken into steps

    - Steps in `packages/chili/src/step/` (pointStep, selectStep, etc.)
    - Handle user input and validation

6. **Snapping System**: Sophisticated snapping with tracking
    - Object snapping, plane snapping, axis tracking
    - Located in `packages/chili/src/snap/`

### Working with Commands

Commands extend `ICommand` and are organized by category:

```typescript
// Example command in packages/chili/src/commands/create/
export class BoxCommand extends ICommand {
    async execute(): Promise<void> {
        // Implementation with steps
    }
}
```

Command categories:

- `create/`: Shape creation commands (box, sphere, etc.)
- `modify/`: Transformation commands (move, rotate, fillet, etc.)
- `measure/`: Measurement tools
- `application/`: File operations

### UI Framework

Custom reactive UI system:

- Components use property decorators for reactivity
- CSS modules for styling (`.module.css`)
- Ribbon interface for command organization
- Property panels with type-specific editors

### Testing Configuration

- Jest with ESM support (`extensionsToTreatAsEsm: [".ts"]`)
- Tests in each package's `test/` directory
- JSDOM environment for UI testing
- CSS modules mocked via `styleMock.js`

## Important Implementation Details

- **Document Version**: Current version 0.6 (increment when changing serialization)
- **WebAssembly**: OpenCascade compiled to WASM, initialized asynchronously
- **Internationalization**: Multi-language support (en, zh-cn, ja) via `chili-core/src/i18n/`
- **Pre-commit Hooks**: Automatic formatting with prettier and clang-format
- **Build Tool**: Uses Rspack (faster Webpack alternative) for development and production
- **License**: GNU Affero General Public License v3.0 (AGPL-3.0)

## Core Development Patterns

### WASM Integration

- C++ OpenCascade bindings in `cpp/src/` compiled to WebAssembly
- TypeScript wrappers in `chili-wasm` provide JavaScript API
- Use `gc()` helper for memory management with WASM objects
- WASM initialization required before geometry operations

### 3D Face Number Display System

- Face numbers displayed using Three.js sprites with canvas textures
- Multiple calculation methods for face centers:
    1. Bounding box center calculation (primary)
    2. Triangle mesh centroid with area weighting
    3. Parametric surface center (fallback)
- Box geometry refinement using normal vectors to determine accurate face positions
- Face numbering based on normal direction (X/Y/Z axis alignment)

### Reactive UI System

- Custom property decorators for data binding and reactivity
- CSS modules for component styling (`.module.css`)
- UI components in `chili-ui` with ribbon interface pattern
- Property panels adapt to selected object types

### Service Architecture

- Services implement `IService` interface with lifecycle methods
- Registration via `AppBuilder.getServices()`
- Key services: `CommandService`, `HotkeyService`, `EditorService`, `StepUnfoldService`
- Services can be registered at application startup or dynamically

### Error Handling

- Use `Result<T, E>` pattern for operations that may fail
- Consistent error propagation through Result chains
- Logger utility for debug/info/warn/error messages
