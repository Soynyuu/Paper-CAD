# Paper-CAD

**建物模型制作のための 3D → 2D 展開図（SVG）自動生成 CAD**
![paper_cad](https://github.com/user-attachments/assets/6b45ec18-dbe1-4e00-812e-2045f14d8a6f)

[![Python](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.8-blue.svg)](https://www.typescriptlang.org/)
[![未踏ジュニア](https://img.shields.io/badge/未踏ジュニア-2025-orange.svg)](https://jr.mitou.org/)

## 概要

Paper-CAD は、ブラウザで建物の 3D モデルを作成・インポートし、紙模型用の 2D 展開図（SVG）へ自動変換する Web ベース CAD です。OpenCASCADE を利用した高精度な展開処理で、設計負担を大きく削減します。

## 主な特徴

- **モデリング**: 3D モデル作成、STEP インポート、3D リアルタイム表示
- **展開**: 折り線・切り線の分類、面番号付与、A4/A3/Letter に対応
- **出力**: SVG を中心に、印刷・加工に適したレイアウトを生成

## クイックスタート

前提:
- Node.js 18 以上
- Python 3.10 以上（Conda 推奨）

### バックエンド
```bash
cd backend
conda env create -f environment.yml
conda activate paper-cad
python main.py  # http://localhost:8001
```

### フロントエンド
```bash
cd frontend
npm install
npm run dev  # http://localhost:8080
```

## 実行モード

### 開発モード
```bash
# backend
python main.py

# frontend (別ターミナル)
npm run dev
```

### デモモード（本番相当の最適化）
```bash
# backend
ENV=demo python main.py

# frontend (別ターミナル)
npm run demo
```

### 本番ビルド/デプロイ
```bash
# frontend
npm run build
npm run deploy:production

# backend
docker compose up -d
```

## 開発コマンド（補足）

フロントエンド:
- `npm run build:wasm`: C++ WebAssembly モジュールをビルド
- `npm test` / `npm run testc`: Jest テスト（`testc` はカバレッジ付き）
- `npm run format`: Prettier + clang-format

バックエンド:
- `pytest`: テスト実行
- `pytest tests/citygml/streaming/`: CityGML ストリーミング関連のみ

## 設定（環境変数）

フロントエンド（ビルド時に埋め込み）:
- `STEP_UNFOLD_API_URL`（必須）: `http://localhost:8001/api`
- `STEP_UNFOLD_WS_URL`（任意）: `ws://localhost:8001/ws/preview`

`.env.development` / `.env.demo` / `.env.production.example` を使用します。

バックエンド:
- `PORT`（デフォルト 8001）
- `FRONTEND_URL`（CORS 用）
- `CORS_ALLOW_ALL`（開発向け）

`.env.development` / `.env.demo` / `.env.production` を使用します。

## API 例

```bash
curl -X POST \
  -F "file=@building.step" \
  -F "page_format=A4" \
  -F "scale_factor=0.01" \
  "http://localhost:8001/api/step/unfold" \
  -o building.svg
```

## プロジェクト構成（AI 向け詳細）

人が流し読みするよりも、エージェントが正確に構造を把握できることを優先しています。

```
Paper-CAD/
├── frontend/                          # TypeScript monorepo（npm workspaces）
│   ├── packages/
│   │   ├── chili-web/                 # フロントエンド入口（index.ts など）
│   │   ├── chili/                     # メインアプリケーション
│   │   ├── chili-ui/                  # Web Components + CSS Modules UI
│   │   ├── chili-core/                # Document/Model/Material/Selection などのコア
│   │   ├── chili-three/               # Three.js 連携・3D 描画
│   │   ├── chili-wasm/                # WebAssembly バインディング
│   │   ├── chili-controls/            # 操作/入力系の補助
│   │   ├── chili-geo/                 # 幾何/座標補助
│   │   ├── chili-vis/                 # 可視化ユーティリティ
│   │   ├── chili-storage/             # 永続化/ストレージ
│   │   └── chili-builder/             # ビルド補助
│   ├── cpp/                           # OpenCASCADE ベース C++ → WASM
│   ├── rspack.config.js               # ビルド設定
│   └── .env.*                         # フロント用環境変数
├── backend/                           # FastAPI サーバー
│   ├── api/                           # REST API ルーティング（endpoints.py）
│   ├── core/                          # 展開パイプライン
│   │   ├── file_loaders.py            # STEP/BREP 読み込み
│   │   ├── geometry_analyzer.py       # 面/エッジ/隣接解析
│   │   ├── unfold_engine.py           # 3D→2D 展開エンジン
│   │   ├── layout_manager.py          # 配置/レイアウト
│   │   ├── svg_exporter.py            # SVG 出力
│   │   ├── pdf_exporter.py            # PDF 出力
│   │   └── step_exporter.py           # STEP 書き出し
│   ├── services/
│   │   ├── step_processor.py          # パイプライン統合
│   │   ├── plateau_fetcher.py         # PLATEAU 連携
│   │   └── citygml/                   # CityGML → STEP 変換（多層構造）
│   │       ├── core/                  # 型・定数
│   │       ├── utils/                 # XML/XLink/ログ
│   │       ├── parsers/               # 座標/ポリゴン解析
│   │       ├── geometry/              # ワイヤ/面/シェル構築
│   │       ├── transforms/            # CRS 変換/リセンタリング
│   │       ├── lod/                   # LOD 抽出戦略
│   │       └── pipeline/              # オーケストレーター
│   ├── models/                        # Pydantic モデル
│   ├── utils/                         # 共有ユーティリティ
│   ├── tests/                         # pytest テスト
│   ├── config.py                      # CORS/OCCT 設定
│   └── main.py                        # FastAPI 起動
├── docs/                              # 運用・最適化ドキュメント
├── AGENTS.md                          # Contributor ガイド
└── CLAUDE.md                          # アーキテクチャ詳細（AI 向け）
```

## アーキテクチャ概要（AI 向け）

### フロントエンド
- **入口**: `frontend/packages/chili-web/src/index.ts`
- **UI**: `chili-ui` の Web Components、CSS Modules を使用
- **3D**: `chili-three` が Three.js を統合
- **CAD カーネル**: `frontend/cpp/` の C++ を WASM 化して `chili-wasm` から呼び出し
- **設定**: `STEP_UNFOLD_API_URL` はビルド時注入（`.env.*`）

### バックエンド
- **主 API**: `POST /api/step/unfold`（STEP → SVG/JSON）
- **処理フロー**: `step_processor.py` → `file_loaders.py` → `geometry_analyzer.py` → `unfold_engine.py` → `layout_manager.py` → `svg_exporter.py`
- **CityGML**: `services/citygml/` 以下に多層構造（LOD 抽出と変換パイプライン）

### 重要な注意
- OpenCASCADE が未インストールでも API は起動しますが、STEP 展開系は 503 になります。
- フロントエンドは `npm install` を `frontend/` で実行する必要があります（workspaces 依存）。

### CityGML 変換の必須フェーズ（AI 注意点）
- **PHASE:0** 座標のリセンタリング（精度劣化を防ぐ）
- **PHASE:1** XLink インデックス構築（参照解決の前提）
- **PHASE:2-6** LOD 抽出 → 形状構築 → 検証
- **PHASE:7** STEP 出力

## 開発に参加する

Issue/PR を歓迎します。変更点・背景・再現手順（必要なら SVG のスクショ）を添えてください。コミットは `feat: ...` / `fix: ...` など短く明確に。

## ライセンス

MIT License - 詳細は[LICENSE](LICENSE)をご覧ください。

## 謝辞

- OpenCASCADE Technology
- 一般社団法人未踏 未踏ジュニア（2025年度採択プロジェクト）
