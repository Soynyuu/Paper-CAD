# Repository Guidelines

This repository hosts the Paper-CAD landing page built with Vite, React, TypeScript, and Tailwind CSS.

## Project Structure & Module Organization
- `src/` holds the React entry points (`main.tsx`, `App.tsx`) plus global styles in `index.css`.
- `public/` contains static assets served as-is (favicons, images).
- `index.html` is the Vite HTML entry; build/config files live at the root (`vite.config.ts`, `tsconfig*.json`, `tailwind.config.js`, `postcss.config.js`).
- `dist/` is generated output from builds; do not edit by hand.

## Build, Test, and Development Commands
- `npm install`: install dependencies.
- `npm run dev`: start the dev server with hot reload.
- `npm run build`: typecheck (`tsc`) and produce a production build in `dist/`.
- `npm run preview`: serve the production build locally.
- `npm run lint`: run ESLint over `ts`/`tsx` sources.

## Coding Style & Naming Conventions
- Use TypeScript + React function components in `*.tsx`.
- Indentation is 2 spaces; keep semicolons and follow existing formatting.
- Component files use PascalCase (e.g., `HeroSection.tsx`); variables and props use camelCase; hooks start with `use`.
- Styling is primarily Tailwind utility classes in JSX, with shared globals in `src/index.css`.

## Testing Guidelines
- No automated test runner is configured yet; rely on `npm run lint` and manual browser checks.
- If adding tests, place them under `src/` (e.g., `src/__tests__/App.test.tsx`) and add a corresponding script in `package.json`.

## Commit & Pull Request Guidelines
- Commit messages follow conventional prefixes such as `feat:`, `fix:`, or `chore:` with a short imperative subject.
- PRs should include a concise summary, rationale, and verification steps (e.g., `npm run dev` or `npm run build`), plus screenshots for UI/layout changes.
