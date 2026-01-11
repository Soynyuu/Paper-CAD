# Repository Guidelines

## Project Structure & Module Organization
`frontend/` は TypeScript の monorepo（Rspack）で、`packages/chili-*` に機能別モジュールがあります。アプリの入口は `frontend/packages/chili-web/`、UI は `chili-ui`、ドキュメント/モデルの中核は `chili-core` です。C++ の CAD カーネルは `frontend/cpp/` で WASM へビルドされます。`backend/` は FastAPI サーバーで、展開パイプラインは `core/`、API ルーティングは `api/`、外部連携は `services/` にあります。テストは `frontend/packages/*/test/` と `backend/tests/`、運用ドキュメントは `docs/`、LP 素材は `lp/` に配置されています。

## Build, Test, and Development Commands
以下のディレクトリで実行してください。
```bash
cd backend
conda env create -f environment.yml
conda activate paper-cad
python main.py            # API http://localhost:8001
ENV=demo python main.py   # demo mode
pytest                    # backend tests
```
```bash
cd frontend
npm install
npm run dev               # UI http://localhost:8080
npm run build             # production build
npm run build:wasm         # build C++ WASM kernel
npm test                  # Jest tests
npm run format            # Prettier + clang-format
```

## Coding Style & Naming Conventions
TS/JS/CSS/JSON/MD は Prettier で整形（2-space）。C++ は clang-format の Webkit スタイル（`npm run format`）。Python は 4-space で PEP8 に近い既存スタイルに合わせます。パッケージ名は `chili-*`、コンポーネントは PascalCase、変数は camelCase。テストは `*.test.ts(x)`（フロント）と `test_*.py`（バックエンド）です。

## Testing Guidelines
フロントエンドは Jest を使用し、`frontend/packages/*/test/` に配置します（例: `npm test -- packages/chili-core/test/observer.test.ts`）。バックエンドは pytest で `backend/tests/` に配置します（例: `pytest tests/citygml/streaming/ -v`）。幾何・出力・PLATEAU 連携の変更は回帰テストを追加してください。

## Commit & Pull Request Guidelines
コミットは `feat:`, `fix:`, `docs:` などの短い接頭辞＋命令形サマリを推奨し、`wip` は避けてください。PR には概要・背景・テスト結果を必ず書き、UI/SVG 変更時はスクリーンショットや GIF を添付し、関連 Issue をリンクしてください。

## Configuration & Environment
フロントのビルド時環境変数は `.env.*` で `STEP_UNFOLD_API_URL`（必須）と `STEP_UNFOLD_WS_URL`（任意）を設定します。バックエンドは `.env.*` で `PORT`, `FRONTEND_URL`, `CORS_ALLOW_ALL` を設定します。前提は Node.js 18+ と Python 3.10（Conda 推奨）。OpenCASCADE がない場合は STEP 展開系の API が 503 を返します。
