# Paper-CAD

**建物模型制作のための 3D → 2D 展開図（SVG）自動生成 CAD**
<img width="1935" height="1233" alt="image" src="https://github.com/user-attachments/assets/ebe07401-d143-4925-973b-8c7edd43f144" />


[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.8-blue.svg)](https://www.typescriptlang.org/)
[![未踏ジュニア](https://img.shields.io/badge/未踏ジュニア-2025-orange.svg)](https://jr.mitou.org/)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.0-4baaaa.svg)](CODE_OF_CONDUCT.md)

## 概要

Paper-CAD は、ブラウザで建物の 3D モデルを作成・インポートし、紙模型用の 2D 展開図（SVG）へ自動変換する Web ベース CAD です。OpenCASCADE を利用した高精度な展開処理で、設計負担を大きく削減します。

## 主な特徴

- **モデリング**: 3D モデル作成、STEP インポート、3D リアルタイム表示
- **展開**: 折り線・切り線の分類、面番号付与、A4/A3/Letter に対応
- **出力**: SVG / PDF 形式で、印刷・加工に適したレイアウトを生成
- **都市モデル対応**: CityGML や PLATEAU のインテグレーションが実装済み。建物名を指定するだけで建物がインポートできます。
- **ランディングページ**: 製品紹介用の LP が `/lp` に独立して実装されています。

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

### ランディングページ
```bash
cd lp
npm install
npm run dev  # http://localhost:5173
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

### ランディングページビルド
```bash
cd lp
npm run build
npm run preview  # ビルドした成果物をプレビュー
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

ランディングページ (`/lp`):
- `npm run dev`: 開発サーバー（Vite）
- `npm run build`: プロダクションビルド
- `npm run preview`: ビルド成果物のプレビュー

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

## CityGML Cache Setup（オプション、東京23区向け）

東京23区のPLATEAU CityGMLデータを事前ダウンロードし、処理速度を10-50倍高速化できます。

### 概要
- **データサイズ**: 圧縮ZIP 500MB-1GB、展開後2-3GB
- **対象**: 東京23区すべて（area_code: 13101-13123）
- **実装方式**: セットアップスクリプトで事前ダウンロード（オプトイン）

### 前提条件
- 3-5GB以上の空きディスク容量
- 安定したインターネット接続（30-60分のダウンロード時間）
- Conda環境: `conda activate paper-cad`

### インストール手順

#### 1. データセット情報の準備
まず、`tokyo23_datasets.json`を生成します。ClaudeにPLATEAU MCPツールを使用してファイルを生成するよう依頼してください:

```json
[
  {
    "area_code": "13101",
    "ward_name": "千代田区",
    "dataset_id": "d_13101_bldg",
    "year": 2023,
    "registration_year": 2024,
    "open_data_url": "https://assets.cms.plateau.reearth.io/...",
    "lod_levels": ["LOD1", "LOD2"]
  },
  ...
]
```

#### 2. セットアップスクリプトの実行
```bash
cd backend
python scripts/setup_citygml_cache.py --datasets-json tokyo23_datasets.json
```

**期待される出力:**
```
Checking disk space...
✓ 8.5 GB available
Loading Tokyo 23 wards dataset information...
Found 23 wards

[1/23] 千代田区 (13101)
  Downloading ZIP... ████████████ 45.2MB
  Extracting...
  ✓ Cached (150 files, 120.3 MB, 35 mesh codes)

[2/23] 中央区 (13102)
...

Building mesh → ward index...
✓ Index created with 1250 mesh codes

Cache setup complete!
Total wards: 23
Total size: 2.47 GB
```

#### 3. キャッシュの有効化
`backend/.env.development`を編集:
```bash
CITYGML_CACHE_ENABLED=true
CITYGML_CACHE_DIR=data/citygml_cache
```

#### 4. バックエンドの再起動
```bash
python main.py
# 起動ログに以下が表示されればキャッシュが有効:
# [CACHE] Loaded mesh index with 1250 entries
```

### 検証

東京の住所でテスト:
```bash
curl -X POST "http://localhost:8001/api/plateau/search-by-address" \
  -H "Content-Type: application/json" \
  -d '{"address": "東京駅", "radius": 0.001, "limit": 5}'
```

ログに以下が表示されれば成功:
```
[PLATEAU] ✓ Cache HIT: mesh=53393580, ward=13101
```

### トラブルシューティング

**「Insufficient disk space」エラー**
- 5GB以上の空き容量を確保: `df -h` (Unix) または エクスプローラー

**「Failed to download {ward}」エラー**
- ネットワーク接続を確認し、以下でレジューム:
  ```bash
  python scripts/setup_citygml_cache.py --skip-existing --datasets-json tokyo23_datasets.json
  ```

**「Cache MISS」が表示される**
- メッシュコードが東京外の場合は自動的にAPIフォールバック
- キャッシュされていない地域では正常な動作

### メンテナンス

PLATEAUの新データリリース時（通常年1回）にキャッシュを更新:
```bash
rm -rf data/citygml_cache
# 最新のtokyo23_datasets.jsonを再生成
python scripts/setup_citygml_cache.py --datasets-json tokyo23_datasets.json
```

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
│   │   ├── chili-cesium/              # Cesium 3D Tiles for PLATEAU ビルディングピッカー
│   │   ├── chili-react-bridge/        # React 連携ブリッジ
│   │   ├── chili-controls/            # 操作/入力系の補助
│   │   ├── chili-geo/                 # 幾何/座標補助
│   │   ├── chili-vis/                 # 可視化ユーティリティ
│   │   ├── chili-storage/             # 永続化/ストレージ
│   │   └── chili-builder/             # ビルド補助
│   ├── cpp/                           # OpenCASCADE ベース C++ → WASM
│   ├── rspack.config.js               # ビルド設定
│   └── .env.*                         # フロント用環境変数
├── backend/                           # FastAPI サーバー
│   ├── api/                           # REST API ルーティング
│   │   ├── routers/                   # エンドポイント定義
│   │   │   ├── step.py                # POST /api/step/unfold, /unfold-pdf
│   │   │   ├── citygml.py             # POST /api/citygml/to-step
│   │   │   ├── plateau.py             # POST /api/plateau/search-by-address
│   │   │   ├── svg.py                 # SVG 関連エンドポイント
│   │   │   └── system.py              # システム/ヘルスチェック
│   │   ├── endpoints.py               # ルーター登録
│   │   └── helpers.py                 # API ヘルパー関数
│   ├── core/                          # 展開パイプライン
│   │   ├── file_loaders.py            # STEP/BREP 読み込み
│   │   ├── geometry_analyzer.py       # 面/エッジ/隣接解析
│   │   ├── unfold_engine.py           # 3D→2D 展開エンジン
│   │   ├── layout_manager.py          # 配置/レイアウト
│   │   ├── svg_exporter.py            # SVG 出力
│   │   ├── pdf_exporter.py            # PDF 出力
│   │   ├── step_exporter.py           # STEP 書き出し
│   │   └── brep_exporter.py           # BREP 出力
│   ├── services/
│   │   ├── step_processor.py          # パイプライン統合
│   │   ├── plateau_fetcher.py         # PLATEAU 連携
│   │   ├── plateau_api_client.py      # PLATEAU API クライアント
│   │   ├── plateau_mesh_mapping.py    # メッシュコードマッピング
│   │   ├── coordinate_utils.py        # 座標変換ユーティリティ
│   │   └── citygml/                   # CityGML → STEP 変換（多層構造）
│   │       ├── core/                  # 型・定数
│   │       ├── utils/                 # XML/XLink/ログ
│   │       ├── parsers/               # 座標/ポリゴン解析
│   │       ├── geometry/              # ワイヤ/面/シェル構築
│   │       ├── transforms/            # CRS 変換/リセンタリング
│   │       ├── lod/                   # LOD 抽出戦略
│   │       ├── pipeline/              # オーケストレーター
│   │       └── streaming/             # メモリ効率のよいストリーミング処理
│   ├── models/                        # Pydantic モデル
│   ├── utils/                         # 共有ユーティリティ
│   ├── tests/                         # pytest テスト
│   ├── config.py                      # CORS/OCCT 設定
│   └── main.py                        # FastAPI 起動
├── lp/                                # ランディングページ（Vite + React + Tailwind）
│   ├── src/                           # React コンポーネント
│   ├── public/                        # 静的アセット
│   ├── vite.config.ts                 # Vite 設定
│   └── tailwind.config.js             # Tailwind CSS 設定
├── docs/                              # 運用・最適化ドキュメント
├── AGENTS.md                          # Contributor ガイド
└── CLAUDE.md                          # アーキテクチャ詳細（AI 向け）
```

## アーキテクチャ概要（AI 向け）

### フロントエンド
- **入口**: `frontend/packages/chili-web/src/index.ts`
- **UI**: `chili-ui` の Web Components、CSS Modules を使用
- **3D**: `chili-three` が Three.js を統合
- **都市モデル**: `chili-cesium` が Cesium 3D Tiles を使用した PLATEAU ビルディングピッカー機能を提供
- **CAD カーネル**: `frontend/cpp/` の C++ を WASM 化して `chili-wasm` から呼び出し
- **設定**: `STEP_UNFOLD_API_URL` はビルド時注入（`.env.*`）

### バックエンド
- **主 API ルーター**: `api/routers/` 以下に機能別に分離
  - `step.py`: `POST /api/step/unfold`（STEP → SVG/JSON）、`/unfold-pdf`
  - `citygml.py`: `POST /api/citygml/to-step`（CityGML → STEP 変換）
  - `plateau.py`: `POST /api/plateau/search-by-address`（PLATEAU 建物検索）
- **処理フロー**: `step_processor.py` → `file_loaders.py` → `geometry_analyzer.py` → `unfold_engine.py` → `layout_manager.py` → `svg_exporter.py`
- **CityGML**: `services/citygml/` 以下に多層構造（LOD 抽出と変換パイプライン）
- **ストリーミング処理**: `services/citygml/streaming/` でメモリ効率のよい大規模 CityGML 処理

### ランディングページ
- **技術スタック**: Vite + React + Tailwind CSS
- **入口**: `lp/src/`
- **目的**: 製品紹介・マーケティング用のシングルページ

### 重要な注意
- OpenCASCADE が未インストールでも API は起動しますが、STEP 展開系は 503 になります。
- フロントエンドは `npm install` を `frontend/` で実行する必要があります（workspaces 依存）。

### CityGML 変換の必須フェーズ（AI 注意点）
- **PHASE:0** 座標のリセンタリング（精度劣化を防ぐ）
- **PHASE:1** XLink インデックス構築（参照解決の前提）
- **PHASE:2-6** LOD 抽出 → 形状構築 → 検証
- **PHASE:7** STEP 出力

## 開発に参加する

Issue/PR を歓迎します。詳細は [CONTRIBUTING.md](CONTRIBUTING.md) をご覧ください。

- [コントリビューションガイド](CONTRIBUTING.md)
- [行動規範](CODE_OF_CONDUCT.md)
- [セキュリティポリシー](SECURITY.md)

## ライセンス

このプロジェクトは [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) の下で配布されています。

**重要**: このソフトウェアは [chili3d](https://github.com/xiangechen/chili3d) をベースにした派生作品です。chili3d は AGPL-3.0 ライセンスで配布されており、派生作品もそれに従います。

## 謝辞

- **[chili3d](https://github.com/xiangechen/chili3d)** - このプロジェクトのベースとなったオープンソース 3D CAD フレームワーク (Copyright (c) 2022-2025 仙阁)
- OpenCASCADE Technology
- 一般社団法人未踏 未踏ジュニア（2025年度採択プロジェクト）
