# Paper-CAD Gemini Context

This document provides instructional context for Gemini, the AI assistant, to understand and effectively assist with the Paper-CAD project.

## Project Overview

Paper-CAD is a web-based CAD tool designed to simplify the creation of paper models of buildings. It allows users to create or import 3D building models and automatically generates 2D development drawings (in SVG format) that can be printed, cut out, and assembled.

The project is a monorepo consisting of a frontend application and a backend API.

*   **Frontend:** The frontend is a web application built with TypeScript and custom Web Components. It uses Three.js for 3D rendering and includes a WebAssembly component written in C++ for CAD functionalities. The build tool is Rspack.

*   **Backend:** The backend is a Python-based API server built with the FastAPI framework. It utilizes the OpenCASCADE Technology library for the core CAD operations, specifically for unfolding the 3D models into 2D patterns.

## Building and Running

### Backend (FastAPI)

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Set up the Python environment:**
    It is recommended to use Conda to create an environment from the `environment.yml` file.
    ```bash
    conda env create -f environment.yml
    conda activate paper-cad
    ```

3.  **Run the development server:**
    ```bash
    python main.py
    ```
    The backend server will be running at `http://localhost:8001`.

### Frontend (TypeScript/Web Components)

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

3.  **Run the development server:**
    ```bash
    npm run dev
    ```
    The frontend application will be accessible at `http://localhost:8080`.

## Development Conventions

### Testing

*   **Frontend:** Tests are run using Jest.
    ```bash
    cd frontend
    npm test
    ```

*   **Backend:** Tests are run using pytest.
    ```bash
    cd backend
    pytest
    ```

### Code Formatting

*   **Frontend:** Code is formatted using Prettier for TypeScript/JavaScript and clang-format for C++.
    ```bash
    cd frontend
    npm run format
    ```

*   **Backend:** Code is formatted using Black.
    ```bash
    cd backend
    black .
    ```

## Key Files and Directories

*   `README.md`: The main project documentation, including setup instructions and an overview.
*   `backend/`: The backend FastAPI application.
    *   `main.py`: The entry point for the backend server.
    *   `api/endpoints.py`: Defines the API endpoints.
    *   `core/`: Contains the core logic for the CAD operations, including the unfolding engine.
    *   `environment.yml`: The Conda environment definition for the backend.
*   `frontend/`: The frontend web application.
    *   `package.json`: Defines the frontend dependencies and scripts.
    *   `rspack.config.js`: The configuration file for the Rspack build tool.
    *   `packages/`: Contains the different modules of the frontend application.
    *   `cpp/`: The C++ source code for the WebAssembly module.
*   `docs/`: Project documentation.
