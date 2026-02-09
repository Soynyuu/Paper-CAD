# gml2step 配信戦略と抽出方針（暫定結論）

## 前提
- Paper-CAD は変更しない（抽出はコピー＆独立運用）
- 権利はほぼ自分名義（要最終確認：外部PR/他プロジェクトの転用なし）

## 結論（配信形）
**v0.1 は「ライブラリ + CLI + Docker」**で出す。
- ライブラリが中核（研究/GIS/開発者に最重要）
- CLIは導入障壁を下げる（コマンド1発）
- DockerはOCCT込みの確実な実行環境として必須

## OCCT 依存の扱い
- CityGML変換パイプラインは OCCT 依存度が高い（必須機能）
- ただし **PyPI配布との相性が悪い**ため、現実解は以下：
  - **PyPI**: `gml2step`（OCCT不要機能が動く）
  - **CAD機能**: `conda install -c conda-forge pythonocc-core` を明示
  - **Docker**: OCCT込みフル機能版を提供

## PLATEAU 取り込み
- **オプション機能として分離**
- `gml2step[plateau]` もしくは `gml2step.plateau` モジュールとして追加

## 抽出対象（gml2stepに入れる）
### コア（必須）
- `backend/services/citygml/**`
  - streaming / parsers / transforms / utils / lod / geometry / pipeline
- `backend/services/coordinate_utils.py`
  - CRS 判定・推奨投影系（`citygml` コアが参照）

### オプション（plateau）
- `backend/services/plateau_fetcher.py`
- `backend/services/plateau_api_client.py`
- `backend/utils/mesh_utils.py`
- `backend/services/plateau_mesh_mapping.py`
- `backend/data/mesh2_municipality.json`
  - `plateau_api_client` が参照するメッシュ→自治体マッピング

## 抽出対象外（Paper-CADに残す）
### 展開・STEP処理系
- `backend/services/step_processor.py`
- `backend/core/unfold_engine.py`
- `backend/core/layout_manager.py`
- `backend/core/svg_exporter.py`
- `backend/core/pdf_exporter.py`
- `backend/api/routers/step.py`

### 旧実装・不要候補
- `backend/services/step_processor_old.py`
- `backend/core/step_exporter.py`（参照なし）
- `backend/core/brep_exporter.py`（参照なし）
- `backend/services/citygml/legacy/`（空）
- `backend/services/citygml/streaming/memory_profiler.py`（ベンチ用）

## 主要リスク
- **ライセンス**: 既存リポジトリの外部PR混入がないか最終確認
- **OCCT導入性**: pip単体で入らないため、Docker/conda導線を強化
- **期待値ズレ**: gml2step名のままなら「STEP変換必須」と誤解されやすい

## 公開API（v0.1 最小）
- `convert(...)`:
  - 実体は `export_step_from_citygml(...)` の薄いラッパ
- `parse(...)`:
  - 実体は CityGML 読み込み + 基本情報抽出（軽量処理）
- `stream_parse(...)`:
  - 実体は `stream_parse_buildings(...)` の薄いラッパ
- `extract_footprints(...)`:
  - 実体は `parse_citygml_footprints(...)` の薄いラッパ

## 次のステップ（実装順）
1. 新リポジトリ作成（gml2step）
2. `services/citygml/**` + `services/coordinate_utils.py` をコピーして import を置換
3. 最小API設計（`convert / parse / stream_parse / extract_footprints`）
4. CLI追加（Typer想定）
5. Dockerイメージ作成（OCCT込み）
6. PLATEAU機能を optional で追加（`mesh_utils` / マッピングデータ含む）
