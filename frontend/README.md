# Paper‑CAD

High‑performance 3D CAD for the web — powered by WebAssembly (OCCT) + Three.js.

[![Stars](https://img.shields.io/github/stars/xiangechen/chili3d?style=social)](https://github.com/xiangechen/chili3d)
[![License](https://img.shields.io/github/license/xiangechen/chili3d?label=license)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/xiangechen/chili3d/issues)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#development-status)

![Screenshot](./screenshots/screenshot.png)

## Overview

[Paper‑CAD](https://chili3d.com) is an [open‑source](https://github.com/xiangechen/chili3d) browser‑based CAD (Computer‑Aided Design) application written in TypeScript. It compiles OpenCascade (OCCT) to WebAssembly and renders via Three.js to deliver near‑native modeling, editing, and visualization — all in the browser, no install required.

Live deployments:

- Official: [chili3d.com](https://chili3d.com)
- Staging: [chili3d.pages.dev](https://chili3d.pages.dev)

## Features

- **Modeling**: Boxes, cylinders, cones, spheres, pyramids, and more
- **2D Sketching**: Lines, arcs, circles, ellipses, rectangles, polygons, Bézier
- **Operations**: Booleans (union/diff/intersect), extrude, revolve, sweep, loft, offset, section
- **Snapping**: Object/workplane snapping, axis tracking, feature detection, visual guides
- **Editing**: Chamfer, fillet, trim, break, split, feature remove, sub‑shape edit, explode
- **Measure**: Angles, lengths; sum of length/area/volume
- **Docs**: New/open/save, full undo/redo with history, STEP/IGES/BREP import/export
- **UI**: Ribbon‑style UI, assembly hierarchy, dynamic workplanes, 3D viewport + camera recall
- **i18n**: Chinese & English built‑in; contributions for more languages welcome

## Tech Stack

- **Frontend**: TypeScript, Three.js
- **Geometry**: OpenCascade via WebAssembly
- **Build**: Rspack
- **Test**: Jest

## Quick Start

Prerequisites:

- Node.js
- npm

Clone and install:

```bash
git clone https://github.com/xiangechen/chili3d.git
cd Paper-CAD
npm install
```

Run in development:

```bash
npm run dev    # http://localhost:8080
```

## Configuration

Environment variables are injected at build time and centralized via `__APP_CONFIG__`.

- Files: `.env.<NODE_ENV>` is loaded first, then `.env` as fallback.
- Required:
    - `STEP_UNFOLD_API_URL`: Backend API base URL (e.g., `http://localhost:8001/api` or `https://api.example.com/api`).
- Optional:
    - `STEP_UNFOLD_WS_URL`: WebSocket URL for live preview (if used), e.g., `ws://localhost:8001/ws/preview`.

Examples:

1. Local development (`.env` or `.env.development`):

```
STEP_UNFOLD_API_URL=http://localhost:8001/api
STEP_UNFOLD_WS_URL=ws://localhost:8001/ws/preview
```

2. Production (`.env.production` or CI/CD env vars):

```
STEP_UNFOLD_API_URL=https://api.example.com/api
# STEP_UNFOLD_WS_URL=wss://api.example.com/ws/preview
```

Notes:

- Changing env values requires re-build/re-deploy because values are compiled into the bundle via Rspack DefinePlugin.
- Use HTTPS endpoints for production to avoid mixed content errors under HTTPS pages.

Build for production:

```bash
npm run build
```

## Build WebAssembly (OCCT)

If you want to build the OCCT WebAssembly module locally:

1. Install toolchain and deps

```bash
npm run setup:wasm
```

2. Build the module

```bash
npm run build:wasm
```

The compiled artifacts are copied to `packages/chili-wasm/lib`. See `cpp/README.md` for details.

## Development Status

⚠️ Paper‑CAD is in active alpha. Expect:

- Possible breaking API/UX changes
- Ongoing feature development
- Evolving documentation

## Changelog

See releases: https://github.com/xiangechen/chili3d/releases

For Chinese users: media playlist on Bilibili — https://space.bilibili.com/539380032/lists/3108412?type=season

## Contributing

Contributions are welcome — issues, discussions, and PRs.

- Start a thread: https://github.com/xiangechen/chili3d/discussions
- Report bugs/ideas: https://github.com/xiangechen/chili3d/issues
- Style/formatting: `prettier` for TS/JS/CSS/JSON/MD, `clang-format` for C/C++

## Deployment

Cloudflare Pages workflows and CLI commands are available. See `CLOUDFLARE_DEPLOY.md` for step‑by‑step instructions.

Quick reference:

- Set environment variables in Cloudflare Pages project settings:
    - `STEP_UNFOLD_API_URL=https://api.example.com/api`
    - (optional) `STEP_UNFOLD_WS_URL=wss://api.example.com/ws/preview`
- Or provide an `.env.production` in CI before running `npm run build`.

Scripts:

```
npm run deploy            # Deploys current build to default branch environment
npm run deploy:staging    # Deploys to staging branch
npm run deploy:production # Deploys to production (main) branch
```

## License

AGPL‑3.0. For commercial licensing, contact: xiangetg@msn.cn

Full text: [LICENSE](LICENSE)

---

Made with ❤️ by the Paper‑CAD community.
