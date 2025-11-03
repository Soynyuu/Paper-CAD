# Paper-CAD 技術的深みポイント

## 🎯 コア技術の魅力

### 1. 計算幾何学アルゴリズムの実装
**3D曲面から2D展開図への自動変換という非自明な問題を解決**

- **平面性解析**: OpenCASCADE `BRepAdaptor_Surface` で面の曲率・法線方向を精密解析
- **BFS探索による面グループ化**: 隣接する同一平面の面を幅優先探索で効率的に収集（法線類似度閾値 cos値0.95 = 約18度）
- **組み立てタブ自動生成**: エッジ隣接情報から接着用のりしろを自動配置
- **多角形レベル重複回避**: Shapely ライブラリで展開片の正確な衝突判定・最適配置

### 2. WebAssembly × CAD の革新
**業界標準OpenCASCADEをブラウザでネイティブ実行**

- **C++ → WebAssembly コンパイル**: Emscripten で OpenCASCADE カーネル全体を変換
- **ゼロインストール CAD**: ブラウザだけで STEP/BREP 形式の処理が可能
- **クロスプラットフォーム戦略**:
  - フロントエンド: WebAssembly経由で即時モデリング
  - バックエンド: pythonOCC経由で高度な展開処理
  - 両環境で同一の幾何演算ライブラリを活用

### 3. 実世界データとの統合
**PLATEAU 3D都市モデルの完全サポート**

- **LOD階層の包括的対応**:
  - LOD3: 窓・ドアを含む建築モデル (`bldg:lod3Solid`)
  - LOD2: 屋根構造の差別化 (`bldg:lod2Solid`) ← PLATEAUの主要ユースケース
  - LOD1/LOD0: ブロックモデル・フットプリント
  - 複数のフォールバックストラテジーで最大限の堅牢性を実現

- **XLink 参照解決**: CityGML の外部ジオメトリ参照を自動追跡・統合
- **座標系自動変換**: 地理座標（緯度経度）→ 平面座標（メートル単位）の完全自動処理（pyproj活用）
- **住所/施設名検索**: OpenStreetMap Nominatim API 連携で「東京駅」→建物データ取得

### 4. エンドツーエンド処理パイプライン
**STEP入力からSVG/PDF出力まで完全自動化**

```
STEP/CityGML 読込
  ↓ (file_loaders.py)
幾何学解析 - 平面性・曲率・隣接判定
  ↓ (geometry_analyzer.py)
展開エンジン - 3D→2D投影・タブ生成
  ↓ (unfold_engine.py)
レイアウト最適化 - A4/A3用紙への配置
  ↓ (layout_manager.py)
SVG/PDF エクスポート - 印刷可能な展開図
  ↓ (svg_exporter.py / pdf_exporter.py)
```

各モジュールが単一責任原則に従い、テスト可能な設計

### 5. 精度制御とロバスト性
**実世界の不完全なデータに対応**

- **4段階の精度モード**: standard / high / maximum / ultra
- **形状修復レベル**: minimal / standard / aggressive / ultra
- **許容誤差の自動計算**: BoundingBox サイズから最適な tolerance を算出
- **ShapeFix パイプライン**: 不正なジオメトリを自動修復してCAD互換性を確保

### 6. モノレポアーキテクチャ
**フロントエンドは npm workspaces で8パッケージを統合管理**

```
chili/           メインアプリケーション
chili-core/      データ構造（Document, Model, Selection）
chili-ui/        カスタムWebコンポーネント + CSS Modules
chili-three/     Three.js統合
chili-wasm/      WebAssembly バインディング
chili-geo/       幾何演算ユーティリティ
chili-builder/   ビルドヘルパー
chili-web/       エントリポイント
```

各パッケージが独立してテスト・ビルド可能

---

## 📊 技術スタック概要

| 領域 | 技術 | 特徴 |
|------|------|------|
| **CADカーネル** | OpenCASCADE Technology | 業界標準・STEP/BREP完全対応 |
| **幾何演算** | pythonOCC (backend) / WASM (frontend) | 同一ライブラリのクロスプラット |
| **3Dレンダリング** | Three.js | WebGLベース高速描画 |
| **計算幾何** | Shapely / NumPy / SciPy | 衝突判定・凸包・最適化 |
| **座標変換** | pyproj / geopy | EPSG完全対応・ジオコーディング |
| **ビルド** | Rspack (frontend) / FastAPI (backend) | 高速ビルド・型安全API |

---

## 🚀 なぜ技術的に面白いのか

1. **学術的価値**: 3D展開問題は計算幾何学の古典的課題。実用実装は稀
2. **実践的価値**: 実世界の不完全なデータ（PLATEAU）を堅牢に処理
3. **アーキテクチャ**: WebAssembly × Python のハイブリッド戦略
4. **スケーラビリティ**: LOD階層・マルチページ対応で複雑な建物にも対応
5. **オープンソース**: すべてのアルゴリズムがソースコードで公開・検証可能

---

**Paper-CAD** は、古典的CAD技術と最新Web技術を融合し、「3D建物を紙で再現する」という具体的問題を通じて、計算幾何学・WebAssembly・実世界データ統合の最前線を実装したプロジェクトです。
