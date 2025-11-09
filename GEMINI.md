# GEMINI.md

## Project Overview

This project, **Paper-CAD**, is a web-based CAD tool designed to automatically generate 2D SVG layouts from 3D building models, simplifying the process of creating paper models.

The project is a monorepo with a `frontend` and a `backend`.

### Frontend

The frontend is a sophisticated TypeScript application built with custom Web Components and the Chili UI Framework. It uses `three.js` for 3D rendering and a WebAssembly module (built from C++ source) for the core CAD functionalities. `rspack` is used as the build tool.

- **Key Technologies:** TypeScript, Custom Web Components, Three.js, WebAssembly (C++/Emscripten), rspack, Chili UI Framework.
- **Directory:** `frontend/`
- **Entry Point:** `frontend/packages/chili/src/application.ts`

### Backend

The backend is a Python-based API server built with the FastAPI framework. It leverages the powerful OpenCASCADE Technology (OCCT) via `pythonocc-core` for the CAD processing and unfolding algorithms. It's designed to be containerized with Docker or Podman.

- **Key Technologies:** Python, FastAPI, OpenCASCADE Technology (OCCT), pythonocc-core, uvicorn.
- **Directory:** `backend/`
- **Entry Point:** `backend/main.py`

## Building and Running

### Prerequisites

- Node.js 18+
- Python 3.10+
- Conda (recommended)

### Backend Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```
2.  **Create and activate the Conda environment:**
    ```bash
    conda env create -f environment.yml
    conda activate paper-cad
    ```
3.  **Start the server:**
    ```bash
    python main.py
    ```
    The backend will be running at `http://localhost:8001`.

### Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```
2.  **Install dependencies:**
    ```bash
    npm install
    ```
3.  **Start the development server:**
    ```bash
    npm run dev
    ```
    The frontend will be running at `http://localhost:8080`.

## Development Conventions

### Testing

-   **Frontend:** Run tests using `npm test` in the `frontend` directory.
-   **Backend:** Run tests using `pytest` in the `backend` directory.

### Formatting

-   **Frontend:** Run `npm run format` in the `frontend` directory to format TypeScript, JavaScript, CSS, JSON, and Markdown files with Prettier, and C/C++ files with clang-format.
-   **Backend:** Run `black .` in the `backend` directory to format Python files.

### Commits

This project uses `simple-git-hooks` and `lint-staged` to automatically format files before committing.
