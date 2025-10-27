<div align="center">
  <img src="logo.png" alt="Paper-CAD logo" width="400">
  <h1>Paper-CAD Backend</h1>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal.svg)](https://fastapi.tiangolo.com/)
  [![OpenCASCADE](https://img.shields.io/badge/OpenCASCADE-7.9.0-green.svg)](https://www.opencascade.com/)
  [![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](https://www.docker.com/)
  [![Mitou Junior](https://img.shields.io/badge/未踏ジュニア-2025-orange.svg)](https://jr.mitou.org/)
  
  <p><strong>3D STEP を高精度な 2D ペーパークラフト SVG に。シンプルな API、実用的なレイアウト、印刷まで一気通貫。</strong></p>
</div>

English: A tiny FastAPI service that unfolds STEP into print‑ready SVG papercraft. Powered by OpenCASCADE.

## 特長

- 📐 STEP→SVG: 3D（.step/.stp）から2D展開図を自動生成
- 🧩 折/切/タブ: 折り線・切り線・組み立てタブを描画
- 🖨️ レイアウト: `canvas`/`paged`（A4/A3/Letter、縦横）
- 🔢 面番号: 面番号データの返却に対応（オプション）
- 🔄 スケール: `scale_factor` で簡単スケーリング
- 🧰 API/CLI 友好: SVGまたはJSONで取得しワークフローに組み込みやすい

## クイックスタート

前提: Conda もしくは Python 3.10 が利用可能

```bash
# 1) Clone
git clone https://github.com/soynyuu/Paper-CAD
cd Paper-CAD/backend

# 2) Create env (Conda 推奨)
conda env create -f environment.yml && conda activate paper-cad

# 3) Run API (dev)
python main.py  # http://localhost:8001

# 4) Health check
curl http://localhost:8001/api/health
```

STEP を送って SVG を受け取る（cURL）

```bash
curl -X POST \
  -F "file=@example.step" \
  "http://localhost:8001/api/step/unfold" \
  -o output.svg
```

JSON で受け取る（SVG文字列や面番号を含めたい場合）

```bash
curl -X POST \
  -F "file=@example.step" \
  -F "output_format=json" \
  -F "return_face_numbers=true" \
  "http://localhost:8001/api/step/unfold" | jq .stats
```

## Docker/Podman

```bash
# Build & run (Docker)
docker build -t paper-cad .
docker compose up -d
curl http://localhost:8001/api/health

# Podman helper
bash podman-deploy.sh build-run
```

## プロジェクト構成

```
core/            # 展開パイプライン（I/O・解析・展開・レイアウト・エクスポート）
  file_loaders.py
  geometry_analyzer.py
  unfold_engine.py
  layout_manager.py
  svg_exporter.py
  step_exporter.py
api/             # FastAPI ルーター/設定
  endpoints.py
  config.py
services/        # STEP 処理ヘルパ
  step_processor.py
models/, utils/  # 共有型/ユーティリティ
tests & examples # test_*.py, test_*.sh, sample outputs
```

## 設定（環境変数）

- `PORT`: API のポート（デフォルト: 8001）
- `FRONTEND_URL`: CORS 許可オリジン（例: `http://localhost:3001`）
- `CORS_ALLOW_ALL`: すべて許可（`true`/`false`、開発向け）

`.env.development` / `.env.production` を用意すると自動で読み込まれます。

## API ドキュメント

- OpenAPI UI: `http://localhost:8001/docs`（Swagger UI）/ `http://localhost:8001/redoc`
- 詳細は `API_REFERENCE.md` を参照

主要エンドポイント（抜粋）

- `POST /api/step/unfold` STEP→SVG/JSON 変換
  - フォーム: `file` (必須), `layout_mode`, `page_format`, `page_orientation`, `scale_factor`, `output_format`, `return_face_numbers`
- `GET /api/health` ヘルスチェック

## 開発

スタイル: Python 3.10 / PEP 8, 4-space indent, type hints。I/O は `file_loaders`、ジオメトリは `geometry_analyzer`、レイアウトは `layout_manager`、エクスポートは `svg_exporter` / `step_exporter` に分離。

```bash
# Run (dev)
python main.py

# Tests / Examples
python test_polygon_overlap.py
bash test_layout_modes.sh
python test_brep_export.py
```

OpenCASCADE (OCCT) が未インストールでも API は起動します（機能は制限されます）。

## CityGML→STEP（実験的）

PLATEAU の CityGML から STEP を生成する高精度パイプラインを提供。

### 概要

- **方式**: gml:Solid ジオメトリ抽出 → B-Rep構築 → STEP(AP214CD) エクスポート
- **対応構造**:
  - ✅ gml:Solid（exterior/interior shells、cavity対応）
  - ✅ gml:CompositeSurface / gml:MultiSurface
  - ✅ bldg:BuildingPart（階層的な建物構造）
  - ✅ XLink参照（xlink:href）による共有ジオメトリ
- **座標変換**: 自動CRS検出と日本平面直角座標系への変換（pyproj）
- **適応的許容誤差**: 座標範囲の0.1%を自動計算（1e-6〜10.0mm）
- **STEP出力**: AP214CD スキーマ、MM単位、1e-6精度、CAD互換性最適化

### 使い方

```bash
# 事前: conda 環境を有効化（OCCT が必要）
conda activate paper-cad

# サンプル（samples/minimal_building.gml → output/minimal_building.step）
python test_citygml_to_step.py --debug

# 任意の CityGML を直接指定
python services/citygml_to_step.py input.gml output.step --default-height 10 --limit 50 --debug
```

### サポートされる GML 構造

**Building 抽出**:
```xml
<bldg:Building gml:id="BLDG_123">
  <bldg:lod1Solid>
    <gml:Solid>
      <gml:exterior>...</gml:exterior>
      <gml:interior>...</gml:interior>  <!-- cavity対応 -->
    </gml:Solid>
  </bldg:lod1Solid>
  <bldg:consistsOfBuildingPart>  <!-- 階層的な部品 -->
    <bldg:BuildingPart>...</bldg:BuildingPart>
  </bldg:consistsOfBuildingPart>
</bldg:Building>
```

**XLink 参照**:
```xml
<gml:surfaceMember xlink:href="#SURFACE_456"/>
```

**座標系**:
- 自動検出: `srsName` 属性から EPSG コードを抽出
- 地理座標系（EPSG:6697等）は平面直角座標系（EPSG:6669〜6687）へ自動変換
- 緯度経度から最適なJapan Plane Rectangular CS ゾーンを選択

### 制限事項と今後の展望

**現在の制限**:
- 非平面サーフェス: ShapeFix で近似修正（NURBS/ベジェ曲面への完全対応は将来的課題）
- TexturedSurface/Appearance: 未対応（ジオメトリのみ）
- TerrainIntersectionCurve: 未対応

**今後の展望**:
- CityJSON 経由の入力対応
- マルチスレッド処理による大規模データセット対応
- 詳細なエラーレポート（建物ID別の成功/失敗）

## よくある質問

- サポート拡張子は？ → `.step`/`.stp`
- 出力は？ → SVG（ファイル返却）/ JSON（文字列返却）
- レイアウトは？ → `canvas`（単一キャンバス）/ `paged`（A4/A3/Letter、縦横）

## ロードマップ

- Nesting 最適化（面配置の自動最密化）
- タブ生成の詳細制御（角丸/実寸幅）
- 大規模モデル向けの分割/ストリーミング
- 追加フォーマット入出力（BRepなど）

## 貢献方法

Issue/PR 歓迎です。変更点・背景・再現手順（必要なら SVG のスクショ）を添えてください。コミットは「fix: ...」「feat: ...」のように短く明確に。

## ライセンス

MIT License

## 謝辞

- OpenCASCADE Technology
- 一般社団法人未踏 未踏ジュニア（2025）

— Made with ❤️ by the Paper-CAD team
