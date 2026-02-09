 目次
1. [プロジェクト概要](#プロジェクト概要)
2. [解決する課題](#解決する課題)
3. [ターゲットユーザー](#ターゲットユーザー)
4. [主要機能](#主要機能)
5. [プロジェクト構成](#プロジェクト構成)
6. [API設計](#api設計)
7. [ドキュメント計画](#ドキュメント計画)
8. [プロモーション計画](#プロモーション計画)
9. [実行タイムライン](#実行タイムライン)
10. [Paper-CADとの関係](#paper-cadとの関係)
---
 プロジェクト概要
| 項目 | 内容 |
|------|------|
| **プロジェクト名** | gml2step |
| **タグライン** | CityGML to STEP converter - Make CityGML usable |
| **ライセンス** | LGPL-3.0 |
| **公開形態** | PyPI + CLI + Docker（Web API） |
| **言語** | Python 3.10+ |
| **主な依存** | pythonocc-core（オプション）, pyproj, numpy |
 コンセプト
gml2step
〜 CityGMLの「開けない」を解決する 〜
CityGML処理に必要なすべてを、Pythonでシンプルに。
---
## 解決する課題
### CityGMLの「使いにくさ」
CityGMLは都市の3Dモデルを記述する国際標準フォーマット（OGC標準）。
日本ではPLATEAUプロジェクトで全国の都市が3Dモデル化されている。
**問題: CityGMLは「見れない・使えない」**
😭 ユーザーの悩み
┌─────────────────────────────────────────────────────────────┐
│ 「PLATEAUの3Dデータを使いたいけど...」                        │
│                                                             │
│ ❌ CADソフト（Fusion360, AutoCAD）で開けない                │
│ ❌ 3Dプリントできない                                       │
│ ❌ Blenderに読み込めない（プラグインが不安定）              │
│ ❌ ゲームエンジンで使えない                                 │
│ ❌ 大規模ファイル（100MB超）が処理できない                  │
│ ❌ 座標系が複雑で変換方法が分からない                       │
│ ❌ そもそもXMLで何万行もあって何が何だか分からない          │
└─────────────────────────────────────────────────────────────┘
**既存ツールの問題**
| ツール | 問題点 |
|--------|--------|
| **FME** | 商用ソフト、高価（年間数十万円）|
| **citygml4j** | Javaライブラリ、パーサーのみでCAD変換なし |
| **3DCityDB** | データベース向け、軽量な変換には不向き |
| **Blenderプラグイン** | 不安定、CAD精度が出ない |
| **QGIS** | 2D向け、3Dは限定的 |
**→ PythonでCityGMLを包括的に扱えるOSSがない！**
### gml2stepが解決すること
CityGML (.gml)  ───────────>  使える形式
  「開けない」                「どこでも使える」
┌─────────────────────────────────────────────────────────────┐
│ ✅ STEP出力 → CADソフトで編集、3Dプリント                  │
│ ✅ ポリゴン抽出 → Three.js、ゲームエンジン                 │
│ ✅ メタデータ抽出 → データ分析、可視化                     │
│ ✅ 座標変換 → 正しい位置で表示                             │
│ ✅ 大規模ファイル対応 → 都市全体を処理                     │
└─────────────────────────────────────────────────────────────┘
---
## ターゲットユーザー
### 1. 都市計画・建築の研究者
```python
# PLATEAUからダウンロードしたデータを変換
from gml2step import convert
convert("shibuya_bldg.gml", "shibuya.step")
# → FreeCADで開いて体積計算、断面解析などが可能に
ペイン: CityGMLデータをCADで解析したいが、変換方法がない
ゲイン: ワンコマンドでSTEP形式に変換、CADで自由に編集
2. データサイエンティスト・GIS研究者
# 建物メタデータを抽出して分析
from gml2step import parse
buildings = list(parse("city.gml"))
heights = [b.height for b in buildings]
print(f"平均高さ: {sum(heights)/len(heights):.1f}m")
ペイン: 建物データを分析したいが、XMLパースが複雑すぎる
ゲイン: Pythonで簡単にメタデータ抽出、pandasと連携
3. Web/XR開発者
# ポリゴンデータを抽出してThree.jsで表示
for building in parse("area.gml"):
    json_data = {
        "id": building.id,
        "polygons": [p.exterior for p in building.polygons],
        "height": building.height
    }
    # → Three.js, Unity, Unrealに渡す
ペイン: リアルな都市データをアプリに組み込みたい
ゲイン: CAD変換不要でポリゴンデータを直接取得
4. 建築模型・ジオラマ制作者
$ gml2step convert my_town.gml model.step
$ # FreeCADでSTLに変換して3Dプリント！
ペイン: 自分の街の3Dプリント模型を作りたい
ゲイン: コマンド一発で変換、あとは3Dプリント
5. CAD/BIMソフトウェア開発者
# LGPLなので商用製品にも組み込み可能
from gml2step import parse, convert
class MyCADApp:
    def import_citygml(self, path):
        for building in parse(path):
            self.add_building_to_scene(building)
ペイン: 自社製品にPLATEAU連携機能を追加したい
ゲイン: LGPLライブラリとして組み込み、開発工数削減
---
主要機能
機能マップ
┌─────────────────────────────────────────────────────────────┐
│                      gml2step                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  🚀 パーサー     │  │  🔧 CAD変換     │                  │
│  │  (OpenCASCADE   │  │  (OpenCASCADE   │                  │
│  │   不要)         │  │   必要)         │                  │
│  └────────┬────────┘  └────────┬────────┘                  │
│           │                    │                            │
│  ┌────────┴────────────────────┴────────┐                  │
│  │                                       │                  │
│  │  • ストリーミングパーサー            │                  │
│  │  • 座標系自動検出・変換              │                  │
│  │  • メタデータ抽出                    │                  │
│  │  • XLink参照解決                     │                  │
│  │  • LODフォールバック                 │                  │
│  │  • 2Dフットプリント抽出              │                  │
│  │                                       │                  │
│  └───────────────────────────────────────┘                  │
│                                                             │
│  ┌───────────────────────────────────────┐                  │
│  │  CAD変換専用機能                      │                  │
│  │                                       │                  │
│  │  • STEP出力                          │                  │
│  │  • 4段階自動修復                     │                  │
│  │  • ジオメトリ診断                    │                  │
│  │  • BuildingPart統合                  │                  │
│  │                                       │                  │
│  └───────────────────────────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
1. 🚀 ストリーミングパーサー（大規模ファイル対応）
最大の特徴！
┌────────────────────────────────────────────────────────────┐
│  従来方式: 5GBファイル → メモリ48GB使用、処理不能          │
│  gml2step:  5GBファイル → メモリ800MB、処理可能           │
│                                                            │
│  メモリ削減: 98.3%                                         │
│  処理速度:   3-5倍高速                                     │
└────────────────────────────────────────────────────────────┘
# CAD変換なしで使える
from gml2step import stream_parse
for building in stream_parse("huge_file.gml", limit=1000):
    # 1件ずつ処理、メモリを圧迫しない
    process_building(building)
技術的実装:
- SAX-style ET.iterparse() による増分パース
- Building単位でのyield + 即時メモリ解放
- ローカルXLinkインデックス（Building単位）
- 早期終了（limit到達時）
2. 🌍 座標系自動検出・変換
from gml2step import detect_crs, transform_coordinates
# CityGML内のsrsName属性から自動検出
crs = detect_crs("city.gml")
# → "EPSG:6668"（日本測地系2011）
# 日本の平面直角座標系を自動選択
target_crs = select_optimal_crs(lat=35.68, lon=139.76)
# → "EPSG:6677"（東京周辺に最適な系）
対応座標系:
- WGS84 (EPSG:4326)
- 日本測地系2011 (EPSG:6668)
- 日本の平面直角座標系（全19系を自動選択）
- UTM座標系
3. 📊 建物メタデータ抽出
from gml2step import parse
for building in parse("city.gml"):
    print(f"ID: {building.id}")
    print(f"高さ: {building.height}m")
    print(f"LOD: {building.lod_level}")
    print(f"ポリゴン数: {len(building.polygons)}")
    print(f"属性: {building.attributes}")
    # → {"address": "東京都...", "usage": "residential", ...}
抽出可能な属性:
- gml:id - 建物ID
- bldg:measuredHeight - 計測高さ
- uro:buildingHeight - 建物高さ（PLATEAU拡張）
- gen:stringAttribute - 汎用文字列属性
- gen:intAttribute - 汎用整数属性
- uro:buildingIDAttribute - PLATEAU建物ID
4. 🔗 XLink参照解決
CityGMLは複雑なXLink参照を使用：
<bldg:lod2Solid>
  <gml:Solid>
    <gml:exterior xlink:href="#surface_123"/>  ← 別の場所を参照
  </gml:Solid>
</bldg:lod2Solid>
gml2stepは自動的に解決：
# 内部で自動的にXLinkを解決
for building in parse("city.gml"):
    # building.polygonsには参照解決済みのデータが入る
    for polygon in building.polygons:
        print(polygon.exterior)  # 座標が取得できる
5. 🏗️ LOD自動選択とフォールバック
LOD3（詳細）→ LOD2（標準）→ LOD1（簡易）→ LOD0（フットプリント押し出し）
   ↓ なければ    ↓ なければ    ↓ なければ    ↓ フォールバック
# 自動的に最良のLODを選択
for building in parse("city.gml"):
    print(building.lod_level)  # → "LOD2"
    print(building.extraction_method)  # → "lod2Solid//gml:Solid"
LOD優先順位:
1. LOD3 (lod3Solid, lod3MultiSurface)
2. LOD2 (lod2Solid, boundedBy surfaces)
3. LOD1 (lod1Solid)
4. LOD0 (フットプリント + 高さ押し出し)
6. 📐 2Dフットプリント抽出
CAD変換とは別に、純粋なポリゴンデータとして抽出：
from gml2step import extract_footprints
for fp in extract_footprints("city.gml"):
    print(fp.building_id)
    print(fp.exterior)      # [(x1,y1), (x2,y2), ...]
    print(fp.holes)         # 中庭などの穴
    print(fp.height)        # 推定高さ
# GeoJSONとして出力
import json
features = [fp.to_geojson() for fp in extract_footprints("city.gml")]
print(json.dumps({"type": "FeatureCollection", "features": features}))
用途:
- GIS解析用の2Dポリゴン
- 地図アプリでの可視化
- 面積計算、建蔽率計算
7. 🔧 4段階自動修復（CAD変換時）
minimal → standard → aggressive → ultra
   ↓ 失敗     ↓ 失敗      ↓ 失敗     ↓ 最終手段
| レベル | 処理内容 | 使用場面 |
|--------|---------|---------|
| minimal | 基本的なShapeFix | 軽微な問題 |
| standard | トポロジ統合、UnifySameDomain | 中程度の問題 |
| aggressive | 許容値緩和、再構築 | 深刻な問題 |
| ultra | 最強力修復、ShapeFix_Shape | 最後の手段 |
# 自動的にエスカレーション
convert("broken_building.gml", "output.step", fix_level="auto")
# → minimal失敗 → standard失敗 → aggressive成功！
8. 🔍 ジオメトリ診断
from gml2step import diagnose
errors = diagnose("problematic.gml", building_id="BLDG_001")
print(errors)
# → {
#     'is_valid': False,
#     'free_edges_count': 12,
#     'invalid_faces': [3, 7],
#     'shell_closed': False,
#     'error_summary': {
#         'total_edges': 156,
#         'free_edges': 12,
#         'total_faces': 74,
#         'invalid_faces_count': 2
#     }
# }
診断項目:
- フリーエッジ（接続されていない辺）
- 無効な面
- シェルの閉鎖性
- トポロジの整合性
---
プロジェクト構成
ディレクトリ構造
gml2step/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml              # テスト・リント（PR時）
│   │   ├── release.yml         # PyPIリリース（タグ時）
│   │   └── docs.yml            # ドキュメントビルド
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
├── src/
│   └── gml2step/
│       ├── __init__.py         # 公開API
│       ├── py.typed            # 型ヒントマーカー
│       │
│       ├── core/               # 共通基盤
│       │   ├── __init__.py
│       │   ├── types.py        # データ型定義
│       │   ├── constants.py    # 名前空間、定数
│       │   └── exceptions.py   # カスタム例外
│       │
│       ├── parser/             # CityGMLパーサー（ピュアPython）
│       │   ├── __init__.py     # parse(), stream_parse()
│       │   ├── reader.py       # ストリーミングパーサー
│       │   ├── building.py     # Building抽出
│       │   ├── coordinates.py  # 座標抽出
│       │   ├── polygons.py     # ポリゴン抽出
│       │   ├── xlink.py        # XLink解決
│       │   ├── attributes.py   # メタデータ抽出
│       │   └── lod/            # LOD戦略
│       │       ├── __init__.py
│       │       ├── extractor.py
│       │       ├── lod1.py
│       │       ├── lod2.py
│       │       └── lod3.py
│       │
│       ├── transform/          # 座標変換
│       │   ├── __init__.py
│       │   ├── crs.py          # CRS検出・変換
│       │   ├── recenter.py     # 原点リセンタリング
│       │   └── japan.py        # 日本の平面直角座標系
│       │
│       ├── geometry/           # 3Dジオメトリ構築（OpenCASCADE依存）
│       │   ├── __init__.py
│       │   ├── builder.py      # 統合ビルダー
│       │   ├── solid.py        # Solid構築
│       │   ├── shell.py        # Shell構築
│       │   ├── fixer.py        # 形状修復（4段階）
│       │   ├── tolerance.py    # 許容値計算
│       │   └── diagnostics.py  # ジオメトリ診断
│       │
│       ├── export/             # 出力
│       │   ├── __init__.py
│       │   ├── step.py         # STEP出力
│       │   ├── json.py         # JSON出力
│       │   └── geojson.py      # GeoJSON出力
│       │
│       └── cli/                # CLIツール
│           ├── __init__.py
│           └── main.py         # Typer実装
│
├── tests/
│   ├── conftest.py             # pytest fixtures
│   ├── data/                   # テスト用GMLファイル
│   │   ├── simple_building.gml
│   │   ├── lod2_building.gml
│   │   ├── large_file.gml
│   │   └── plateau_sample.gml
│   ├── test_parser.py
│   ├── test_streaming.py
│   ├── test_transform.py
│   ├── test_geometry.py
│   ├── test_export.py
│   └── test_cli.py
│
├── docs/
│   ├── mkdocs.yml
│   ├── index.md
│   ├── getting-started/
│   ├── guides/
│   ├── api/
│   └── ja/                     # 日本語版
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── pyproject.toml
├── LICENSE                     # LGPL-3.0
├── NOTICE
├── README.md
├── CHANGELOG.md
└── CONTRIBUTING.md
pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[project]
name = "gml2step"
version = "0.1.0"
description = "CityGML toolkit - Parse, transform, and convert CityGML to CAD formats"
readme = "README.md"
license = "LGPL-3.0-or-later"
authors = [
    { name = "Soynyuu", email = "your-email@example.com" }
]
keywords = [
    "citygml", "step", "cad", "plateau", "gis",
    "3d-modeling", "urban-planning", "bim", "parser"
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: GIS",
    "Topic :: Multimedia :: Graphics :: 3D Modeling",
]
requires-python = ">=3.10"
dependencies = [
    "pyproj>=3.0.0",
    "numpy>=1.20.0",
]
[project.optional-dependencies]
cad = [
    # pythonocc-coreはcondaでインストール推奨
    # pip install時は空、condaで別途インストール
]
cli = [
    "typer>=0.9.0",
    "rich>=13.0.0",
]
api = [
    "fastapi>=0.100.0",
    "uvicorn>=0.20.0",
]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.0.0",
    "mkdocstrings[python]>=0.23.0",
]
all = [
    "gml2step[cli,api,dev,docs]",
]
[project.scripts]
gml2step = "gml2step.cli.main:app"
[project.urls]
Homepage = "https://github.com/soynyuu/gml2step"
Documentation = "https://soynyuu.github.io/gml2step/"
Repository = "https://github.com/soynyuu/gml2step"
Issues = "https://github.com/soynyuu/gml2step/issues"
[tool.hatch.build.targets.sdist]
include = ["/src"]
[tool.hatch.build.targets.wheel]
packages = ["src/gml2step"]
[tool.ruff]
line-length = 100
target-version = "py310"
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_ignores = true
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=gml2step --cov-report=term-missing"
---
API設計
公開API一覧
# メイン関数
from gml2step import convert, parse, stream_parse
# ユーティリティ
from gml2step import (
    detect_crs,
    list_buildings,
    extract_footprints,
    diagnose,
)
# データ型
from gml2step import (
    Building,
    Polygon3D,
    Footprint,
    ConversionResult,
    LODLevel,
)
# 例外
from gml2step import (
    GMLParseError,
    ConversionError,
    CRSError,
)
convert() - CAD変換
def convert(
    input_path: str | Path,
    output_path: str | Path,
    *,
    # フィルタリング
    buildings: list[str] | None = None,
    lod: LODLevel | str = "auto",
    limit: int | None = None,
    
    # 変換オプション
    method: Literal["solid", "sew", "extrude", "auto"] = "auto",
    precision: Literal["standard", "high", "maximum"] = "standard",
    fix_level: Literal["minimal", "standard", "aggressive", "ultra", "auto"] = "auto",
    
    # 座標系
    source_crs: str | None = None,
    target_crs: str | None = None,
    recenter: bool = True,
    
    # パフォーマンス
    streaming: bool = True,
    
    # デバッグ
    verbose: bool = False,
) -> ConversionResult:
    """
    Convert CityGML to STEP format.
    
    Args:
        input_path: Path to input CityGML file (.gml, .xml)
        output_path: Path to output STEP file (.step, .stp)
        buildings: List of building IDs to convert (None = all)
        lod: Preferred LOD level ("LOD1", "LOD2", "LOD3", "auto")
        limit: Maximum number of buildings to convert
        method: Conversion method
            - "solid": Direct solid extraction
            - "sew": Surface sewing
            - "extrude": Footprint extrusion
            - "auto": Try solid → sew → extrude
        precision: Precision mode for geometry
        fix_level: Shape fixing aggressiveness ("auto" = escalate on failure)
        source_crs: Source CRS override (None = auto-detect)
        target_crs: Target CRS (None = auto-select for Japan)
        recenter: Recenter coordinates near origin (recommended)
        streaming: Use streaming parser for large files
        verbose: Enable verbose logging
        
    Returns:
        ConversionResult with success status and statistics
        
    Example:
        >>> result = convert("plateau.gml", "output.step")
        >>> print(result.success)
        True
        >>> print(result.buildings_converted)
        42
    """
parse() - パース（イテレータ）
def parse(
    input_path: str | Path,
    *,
    buildings: list[str] | None = None,
    lod: LODLevel | str = "auto",
    limit: int | None = None,
    include_attributes: bool = True,
) -> Iterator[Building]:
    """
    Parse CityGML and yield Building objects.
    
    This function does NOT require OpenCASCADE and returns
    pure Python objects with polygon data.
    
    Args:
        input_path: Path to input CityGML file
        buildings: List of building IDs to parse (None = all)
        lod: Preferred LOD level
        limit: Maximum number of buildings
        include_attributes: Extract generic attributes
        
    Yields:
        Building objects with geometry and metadata
        
    Example:
        >>> for building in parse("city.gml"):
        ...     print(f"{building.id}: {building.height}m, {len(building.polygons)} polygons")
    """
stream_parse() - ストリーミングパース
def stream_parse(
    input_path: str | Path,
    *,
    limit: int | None = None,
    buildings: list[str] | None = None,
) -> Iterator[Building]:
    """
    Stream-parse CityGML with minimal memory footprint.
    
    Optimized for large files (100MB+). Uses SAX-style parsing
    with immediate memory release after each building.
    
    Memory usage: O(1 building) ≈ 10-100MB
    vs. regular parse: O(all buildings) ≈ 1-50GB
    
    Args:
        input_path: Path to CityGML file
        limit: Maximum buildings to process (early termination)
        buildings: Filter by building IDs
        
    Yields:
        Building objects (one at a time, memory-efficient)
        
    Example:
        >>> # Process 5GB file with ~800MB memory
        >>> for building in stream_parse("huge_city.gml", limit=1000):
        ...     process(building)
    """
データ型
@dataclass
class Building:
    """Represents a CityGML building with geometry and metadata."""
    id: str
    polygons: list[Polygon3D]
    lod_level: LODLevel
    height: float | None
    parts: list[BuildingPart]
    attributes: dict[str, Any]
    extraction_method: str
    
    @property
    def total_polygons(self) -> int:
        """Total polygon count including parts."""
        ...
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        ...
    
    def to_geojson(self) -> dict:
        """Convert footprint to GeoJSON feature."""
        ...
@dataclass
class Polygon3D:
    """A 3D polygon with coordinates."""
    exterior: list[tuple[float, float, float]]
    interiors: list[list[tuple[float, float, float]]]
    surface_type: str | None  # "WallSurface", "RoofSurface", etc.
@dataclass
class Footprint:
    """2D footprint with height for extrusion."""
    building_id: str
    exterior: list[tuple[float, float]]
    holes: list[list[tuple[float, float]]]
    height: float
    
    def to_geojson(self) -> dict:
        """Convert to GeoJSON feature."""
        ...
@dataclass
class ConversionResult:
    """Result of CityGML to STEP conversion."""
    success: bool
    output_path: str | None
    buildings_converted: int
    buildings_failed: int
    warnings: list[str]
    errors: list[str]
    elapsed_seconds: float
    
    def __bool__(self) -> bool:
        return self.success
class LODLevel(Enum):
    """Level of Detail for CityGML."""
    LOD0 = "LOD0"
    LOD1 = "LOD1"
    LOD2 = "LOD2"
    LOD3 = "LOD3"
    AUTO = "auto"
CLI
# 基本的な変換
gml2step convert city.gml output.step
# オプション付き
gml2step convert city.gml output.step \
  --lod LOD2 \
  --limit 100 \
  --verbose
# 特定の建物のみ
gml2step convert city.gml output.step \
  --building BLDG_001 \
  --building BLDG_002
# 建物一覧
gml2step list city.gml
# ファイル情報
gml2step info city.gml
# → File: city.gml
# → CRS: EPSG:6668
# → Buildings: 1,234
# → LOD levels: LOD1, LOD2
# フットプリント抽出（GeoJSON）
gml2step footprints city.gml --output footprints.geojson
# 診断
gml2step diagnose city.gml --building BLDG_001
---
ドキュメント計画
構成
docs/
├── index.md                    # ホームページ
│
├── getting-started/
│   ├── installation.md         # インストール（pip, conda, Docker）
│   ├── quickstart.md           # 5分で始める
│   └── examples.md             # 基本的な使用例
│
├── guides/
│   ├── parsing.md              # パーサーの使い方
│   ├── streaming.md            # 大規模ファイルの処理
│   ├── cad-conversion.md       # CAD変換の詳細
│   ├── coordinates.md          # 座標系の取り扱い
│   ├── plateau.md              # PLATEAUデータとの連携
│   ├── cli.md                  # CLIツールガイド
│   ├── docker.md               # Docker/APIの使い方
│   └── troubleshooting.md      # トラブルシューティング
│
├── api/
│   ├── convert.md              # convert()リファレンス
│   ├── parse.md                # parse()リファレンス
│   ├── stream_parse.md         # stream_parse()リファレンス
│   ├── utilities.md            # ユーティリティ関数
│   ├── types.md                # データ型
│   └── exceptions.md           # 例外
│
├── development/
│   ├── contributing.md         # コントリビューションガイド
│   ├── architecture.md         # アーキテクチャ
│   └── changelog.md            # 変更履歴
│
└── ja/                         # 日本語版
    ├── index.md
    ├── getting-started/
    └── guides/
        └── plateau.md          # PLATEAUガイド（日本語）
README.md
 gml2step
> **CityGML toolkit** - Parse, transform, and convert CityGML to CAD formats
[![PyPI](https://img.shields.io/pypi/v/gml2step)](https://pypi.org/project/gml2step/)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/gml2step)](https://pepy.tech/project/gml2step)
---
 🤔 The Problem
CityGML files (like [PLATEAU](https://www.mlit.go.jp/plateau/) data) are powerful but hard to use:
- ❌ Can't open in CAD software
- ❌ Can't 3D print
- ❌ Large files crash your tools
- ❌ Complex coordinate systems
- ❌ XML with thousands of lines
**gml2step** solves all of these.
---
 ✨ Features
 🚀 For Everyone
- **Streaming Parser** - Handle 100MB+ files with minimal memory (98% reduction)
- **Auto CRS Detection** - Automatically detect and transform coordinates
- **LOD Fallback** - Automatically select best available LOD level
- **PLATEAU Ready** - Full support for Japanese PLATEAU extensions
 📊 For Data Scientists
- **Metadata Extraction** - Extract building attributes (height, usage, address...)
- **2D Footprints** - Get building footprints as polygons
- **GeoJSON Export** - Direct export for GIS tools
 🔧 For CAD Users
- **STEP Export** - Industry-standard CAD format
- **4-Stage Auto-Repair** - Automatic geometry fixing
- **Geometry Diagnostics** - Detailed error reporting
---
 🚀 Quick Start
 Installation
# Basic (parser only, no CAD conversion)
pip install gml2step
# With CLI
pip install gml2step[cli]
# With CAD conversion (requires OpenCASCADE)
conda install -c conda-forge pythonocc-core
pip install gml2step[cad]
Python API
from gml2step import convert, parse
# Convert to STEP
convert("city.gml", "output.step")
# Parse buildings (no CAD needed)
for building in parse("city.gml"):
    print(f"{building.id}: {building.height}m")
    print(f"  Polygons: {len(building.polygons)}")
    print(f"  LOD: {building.lod_level}")
# Stream large files (98% less memory)
for building in stream_parse("huge_file.gml", limit=1000):
    process(building)
CLI
# Convert
gml2step convert city.gml output.step
# List buildings
gml2step list city.gml
# File info
gml2step info city.gml
# Extract footprints
gml2step footprints city.gml -o footprints.geojson
---
📖 Documentation
- Getting Started (https://soynyuu.github.io/gml2step/getting-started/)
- API Reference (https://soynyuu.github.io/gml2step/api/)
- PLATEAU Guide (日本語) (https://soynyuu.github.io/gml2step/ja/guides/plateau/)
---
🤝 Contributing
Contributions welcome! See CONTRIBUTING.md (CONTRIBUTING.md).
---
📜 License
LGPL-3.0 - Use freely in commercial products as a library.
---
🙏 Acknowledgments
- Developed as part of Paper-CAD (https://github.com/soynyuu/Paper-CAD) (Mitou Junior 2025)
- Powered by OpenCASCADE (https://www.opencascade.com/) via pythonOCC (https://github.com/tpaviot/pythonocc-core)
---
Made with ❤️ by @soynyuu (https://github.com/soynyuu)
---
## プロモーション計画
### 公開時アナウンス
| タイミング | アクション | プラットフォーム |
|-----------|-----------|-----------------|
| 公開前1週間 | ティーザー投稿 | Twitter/X |
| 公開日 | 正式アナウンス | Twitter/X, GitHub |
| 公開日+1日 | 技術記事（日本語） | Qiita or Zenn |
| 公開日+3日 | 技術記事（英語） | dev.to or Medium |
| 公開日+1週間 | PLATEAUコミュニティ投稿 | PLATEAUコミュニティ |
| 継続 | GIS StackExchange回答 | StackExchange |
### Qiita/Zenn記事の構成
```markdown
# CityGMLの「開けない」を解決するPythonライブラリを作った
## はじめに
PLATEAUの3Dデータ、ダウンロードしたことありますか？
ダウンロードして、開こうとして...開けない。そんな経験ありませんか？
未踏ジュニア2025で「Paper-CAD」というプロジェクトを開発する中で、
CityGML→CAD変換をフルスクラッチで実装しました。
約8,000行のPythonコード、27モジュール。
同じ悩みを持つ人のために、OSSとして公開します。
## CityGMLの「使いにくさ」
[課題の説明]
## gml2stepの特徴
1. ストリーミングパーサー（98%メモリ削減）
2. 座標系自動検出・変換
3. メタデータ抽出
4. 4段階自動修復
...
## 使い方
[コード例]
## PLATEAUデータを3Dプリントしてみる
[チュートリアル]
## 実装の工夫
[技術的なポイント]
## 今後の展望
- Building以外の要素（道路、地形など）
- CityGML 3.0対応
- より多くの出力フォーマット
## おわりに
「開けない」を「開ける」に。
コントリビューション、Issue報告、大歓迎です！
SNS投稿（公開日）
🚀 新しいOSSライブラリ「gml2step」を公開しました！
CityGML（PLATEAU等）を扱うためのPythonツールキットです。
✅ CAD形式（STEP）への変換
✅ 大規模ファイル対応（98%メモリ削減）
✅ 座標系自動検出
✅ メタデータ抽出
✅ CLI & Python API
「PLATEAUのデータ、開けない...」を解決します。
PyPI: pip install gml2step
GitHub: [URL]
#Python #GIS #PLATEAU #OpenSource #CityGML
Awesome Lists への追加申請
- awesome-geospatial (github.com/sacridini/Awesome-Geospatial)
- awesome-gis (github.com/sshuair/awesome-gis)
- awesome-python (github.com/vinta/awesome-python)
---
実行タイムライン
Week 1: 準備
| 日 | タスク |
|----|--------|
| Day 1 | GitHubリポジトリ作成、基本構造セットアップ |
| Day 2 | pyproject.toml、LICENSE、README作成 |
| Day 3 | CI/CD設定（GitHub Actions） |
| Day 4-5 | PyPI名予約確認、プロジェクト名最終確定 |
Week 2-3: コード移植
| 週 | タスク |
|----|--------|
| Week 2 前半 | core/, parser/ モジュール移植 |
| Week 2 後半 | transform/, streaming/ モジュール移植 |
| Week 3 前半 | geometry/, export/ モジュール移植 |
| Week 3 後半 | CLI実装、テスト作成 |
Week 4: 品質・ドキュメント
| 日 | タスク |
|----|--------|
| Day 1-2 | テストカバレッジ向上、型チェック |
| Day 3-4 | ドキュメント作成（MkDocs） |
| Day 5 | Docker設定、最終調整 |
Week 5: 公開
| 日 | タスク |
|----|--------|
| Day 1 | 最終テスト、バージョン確定 |
| Day 2 | PyPIリリース、GitHubリリース |
| Day 3 | 日本語記事公開（Qiita/Zenn） |
| Day 4 | 英語記事公開（dev.to） |
| Day 5 | PLATEAUコミュニティへの告知 |
---
Paper-CADとの関係
段階的な移行
Phase 1: 並行開発
┌─────────────────┐     ┌─────────────────┐
│   Paper-CAD     │     │    gml2step     │
│   (現状維持)     │     │   (新規開発)     │
│                 │     │                 │
│ services/       │     │ src/gml2step/   │
│   citygml/      │ ←──→│   (コピー&改良)  │
└─────────────────┘     └─────────────────┘
Phase 2: 依存関係の追加
┌─────────────────┐     ┌─────────────────┐
│   Paper-CAD     │────→│    gml2step     │
│                 │ pip │                 │
│ requirements:   │     │   (PyPI公開)    │
│   gml2step      │     │                 │
└─────────────────┘     └─────────────────┘
Phase 3: 完全移行
┌─────────────────┐     ┌─────────────────┐
│   Paper-CAD     │────→│    gml2step     │
│                 │     │                 │
│ services/       │     │ (メンテナンス   │
│   citygml/      │     │  対象が一本化)  │
│   (削除)        │     │                 │
└─────────────────┘     └─────────────────┘
互換性維持（移行期間中）
# Paper-CAD側のラッパー（Phase 2）
# backend/services/citygml/__init__.py
try:
    # 新しいライブラリを使用
    from gml2step import convert as _convert
    
    def export_step_from_citygml(gml_path, out_step, **kwargs):
        """Paper-CAD互換のラッパー"""
        result = _convert(gml_path, out_step, **kwargs)
        return result.success, result.output_path or ""
        
except ImportError:
    # フォールバック：従来の実装を使用
    from .pipeline.orchestrator import export_step_from_citygml
---
関連リンク
- Paper-CAD: https://github.com/soynyuu/Paper-CAD
- PLATEAU: https://www.mlit.go.jp/plateau/
- CityGML標準: https://www.ogc.org/standards/citygml
- pythonOCC: https://github.com/tpaviot/pythonocc-core
- OpenCASCADE: https://www.opencascade.com/
---
更新履歴
| 日付 | 内容 |
|------|------|
| 2025-XX-XX | 初版作成 |
---
