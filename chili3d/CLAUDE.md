# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chili3D (formerly Paper-CAD) is a web-based 3D CAD application built with TypeScript, OpenCascade (WebAssembly), and Three.js. It follows a monorepo structure using npm workspaces with 11 packages.

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
npm run testc            # Run tests with coverage
npm test -- packages/chili-core/test/math.test.ts  # Run specific test
npm test -- --watch      # Run tests in watch mode

# Code Quality
npm run format           # Format all code (TypeScript + C++ with clang-format)
npx tsc --noEmit        # Type check (Note: some @types/node errors are expected)
npx prettier --check .   # Check formatting without writing

# Setup & Release
npm install             # Install dependencies
npm run setup:wasm      # Setup WASM dependencies
npm run release         # Run release script
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
- SVG-Edit integration for 2D editing (packages/chili-ui/src/stepUnfold/)

### Testing Configuration

- Jest with ESM support (`extensionsToTreatAsEsm: [".ts"]`)
- Tests in each package's `test/` directory
- JSDOM environment for UI testing
- CSS modules mocked via `styleMock.js`

## Important Implementation Details

- **Document Version**: Current version 0.6 (increment when changing serialization)
- **WebAssembly**: OpenCascade compiled to WASM, initialized asynchronously
- **Internationalization**: Multi-language support (en, zh-cn, ja) via `chili-core/src/i18n/`
- **Pre-commit Hooks**: Automatic formatting with prettier and clang-format via lint-staged
- **Build Tool**: Uses Rspack (faster Webpack alternative) for development and production
- **License**: GNU Affero General Public License v3.0 (AGPL-3.0)
- **TypeScript**: Strict mode enabled with experimental decorators

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
- Dynamic offset calculation to prevent overlap with 3D models

### Reactive UI System

- Custom property decorators for data binding and reactivity
- CSS modules for component styling (`.module.css`)
- UI components in `chili-ui` with ribbon interface pattern
- Property panels adapt to selected object types
- Design system integration with consistent theming

### Service Architecture

- Services implement `IService` interface with lifecycle methods
- Registration via `AppBuilder.getServices()`
- Key services: `CommandService`, `HotkeyService`, `EditorService`, `StepUnfoldService`
- Services can be registered at application startup or dynamically

### Error Handling

- Use `Result<T, E>` pattern for operations that may fail
- Consistent error propagation through Result chains
- Logger utility for debug/info/warn/error messages

## Key Files and Locations

### Configuration Files

- `rspack.config.js`: Build configuration with TypeScript decorators and CSS modules support
- `jest.config.js`: Test configuration with ESM support and CSS mocking
- `package.json`: Monorepo root with workspace definitions
- `tsconfig.json`: TypeScript configuration with strict mode and experimental decorators
- `.prettierrc`: Code formatting rules (4 spaces, 109 char line width)

### Core Implementation Files

- `packages/chili-builder/src/appBuilder.ts`: Application initialization and service registration
- `packages/chili/src/commands/`: All user-facing commands organized by category
- `packages/chili/src/snap/`: Snapping system implementation with object and axis tracking
- `packages/chili/src/step/`: Step-based user interaction handlers
- `packages/chili-three/src/faceNumberDisplay.ts`: 3D face numbering implementation
- `packages/chili-ui/src/stepUnfold/stepUnfoldPanel.ts`: Papercraft unfolding UI panel with SVG-Edit integration

### Integration with External Services

- `StepUnfoldService`: Integrates with backend papercraft service at https;//backend-diorama.soynyuu.com
- Supports STEP export and SVG import for unfolding 3D models
- Face numbering synchronization between 3D view and 2D papercraft
- SVG-Edit integration for 2D editing of unfolded patterns

## Development Workflow

### Adding a New Command

1. Create command class in `packages/chili/src/commands/[category]/`
2. Extend `ICommand` interface
3. Register in ribbon via `packages/chili-builder/src/ribbon.ts`
4. Add i18n keys in `packages/chili-core/src/i18n/`

### Working with WASM

- WASM files pre-built in `packages/chili-wasm/lib/`
- Rebuild with `npm run build:wasm` (requires cmake)
- Always await `initWasm()` before using OpenCascade functions
- Use `gc()` helper for manual memory management

### Testing Guidelines

- Tests located in each package's `test/` directory
- Mock CSS modules using `styleMock.js`
- Use `testDocument.ts` helpers for document testing
- Run specific tests with path: `npm test -- packages/[package]/test/[test].test.ts`

### Code Quality Checks

- Format check: `npx prettier --check .`
- Type check: `npx tsc --noEmit` (Note: some @types/node errors are expected)
- Format fix: `npm run format`
- Pre-commit hooks automatically format staged files

## Debugging Tips

### Face Number Display Issues

- Check `ThreeGeometry.setFaceNumbersVisible()` in packages/chili-three/src/threeGeometry.ts
- Verify `FaceNumberDisplay.generateFromShape()` calculations
- Backend face numbers set via `setBackendFaceNumbers()`
- Check dynamic offset calculations for model size

### Command Execution

- Commands logged in `CommandService`
- Step execution tracked in browser console
- Undo/redo managed by document history

### Build Issues

- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check TypeScript errors: `npx tsc --noEmit`
- Verify WASM module loading in browser DevTools Network tab
- SVG-Edit resources copied via rspack.config.js CopyRspackPlugin

### SVG-Edit Integration

- Resources located in `node_modules/svgedit/dist/editor`
- Override styles in `packages/chili-ui/src/stepUnfold/svgedit-override.css`
- Type definitions in `packages/chili-ui/src/stepUnfold/svgedit.d.ts`
- Initialization in `StepUnfoldPanel.initializeSvgEditor()`
