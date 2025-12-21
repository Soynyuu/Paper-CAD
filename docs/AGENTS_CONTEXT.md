# Paper-CAD プロジェクトコンテキスト - エージェント向けガイド

## 📋 プロジェクト概要（一行説明）

**Paper-CAD は、3D建物モデルを2Dペーパークラフト展開図に自動変換するWebベースCADツールです。**

---

## 🎯 プロジェクトの目的とビジョン

### 核心的な目的
**建物模型制作を、もっと楽しく、もっと簡単に** ("Building model-making - more fun, more simple")

### 解決する課題
従来のペーパークラフト制作では、3D構造を2D展開図に「手作業で設計する」工程が非常に労力がかかっていました。Paper-CADはこの工程を完全自動化し、数秒で精密な展開図を生成します。

```
【従来】3D概念 → 手作業展開設計（数時間〜数日） → 印刷 → 切断 → 組立
【Paper-CAD】3Dモデル → 自動展開（数秒） → 印刷 → 切断 → 組立
```

### ターゲットユーザー
1. **建築模型愛好家** - 趣味で紙模型を作る人
2. **都市計画者・建築家** - 物理プロトタイプが必要な専門家
3. **教育機関** - 建築・空間デザインを学ぶ学生
4. **PLATEAUユーザー** - 日本の3D都市データプラットフォーム利用者

### 社会的意義
- **未踏ジュニア2025採択プロジェクト** - 革新性と社会的インパクトが認められている
- **市民参加型都市計画** - 政府オープンデータ（PLATEAU）から実在建物の物理模型を作成可能
- **技術の民主化** - 専門知識不要で高精度な模型制作を実現

---

## 🏗️ 重要な設計原則（エージェント必読）

### 1. **Unix哲学 "Less is More"**
```
✅ シンプルで明確なコードを書く
✅ 一つのことを正しく行う
✅ 不要な複雑性を避ける
✅ モジュール性を保つ
❌ 過度な抽象化
❌ 不必要な機能追加
❌ 値のハードコーディング
```

### 2. **精密幾何学ファースト**
- **コア価値**: OpenCASCADE Technology による高精度3D→2D変換
- **正確性 > 便利機能**: まず正しく展開することが最優先
- **柔軟性**: 様々な製作方法（紙/厚紙/レーザーカット/CNC）に対応

### 3. **ワークフロー優先**
エージェントがコードを書く際も、以下の順序を守る：
```
1. Research   → 関連ファイルを読み、理解する（コードを書かない）
2. Plan       → 詳細なステップバイステップ計画を作成
3. Implement  → 計画に基づいて実装
4. Verify     → テストを実行し、動作確認
```

### 4. **モジュール設計**
- **フロントエンド**: npm workspaces による6パッケージ構成（過度な分割を避ける）
- **バックエンド**: 7層27モジュール（CityGML処理は Issue #129 でリファクタ済み）
- **平均200行/モジュール** - 可読性と保守性のバランス

---

## 🔧 技術スタック概要

### フロントエンド
- **言語**: TypeScript
- **UI**: カスタムWeb Components + CSS Modules
- **3D**: Three.js レンダリング
- **CAD**: OpenCASCADE (WebAssembly経由)
- **ビルド**: Rspack
- **開発サーバー**: localhost:8080

### バックエンド
- **言語**: Python 3.10+
- **フレームワーク**: FastAPI
- **CAD**: pythonOCC (OpenCASCADE Python bindings)
- **座標変換**: pyproj, Shapely
- **ジオコーディング**: geopy
- **サーバー**: Uvicorn (localhost:8001)
- **環境管理**: Conda

### デプロイ
- **フロントエンド**: Cloudflare Pages
- **バックエンド**: Docker/Podman コンテナ
- **本番URL**:
  - Frontend: https://paper-cad.soynyuu.com
  - Backend: https://backend-paper-cad.soynyuu.com

---

## ⭐ 重要な特徴（他ツールとの差別化）

### 1. **完全自動展開アルゴリズム**
- **ファイル**: `backend/core/unfold_engine.py`
- **手法**: スパニングツリー法 + 平面/円筒/円錐面対応
- **出力**: 折り線（fold lines）と切断線（cut lines）の自動分類

### 2. **PLATEAU深統合** 🇯🇵
```python
# 住所から建物を検索 → 3Dデータ取得 → STEP変換 → 展開 （全自動）
POST /api/plateau/fetch-and-convert
{
  "address": "東京駅",
  "building_id": "bldg_abc123"
}
```
- **LOD3→LOD2→LOD1フォールバック** - 最適なディテールレベルを自動選択
- **BuildingPart統合** - 複数パーツのBoolean融合
- **XLink解決** - CityGMLの参照リンクを自動解決
- **座標系変換** - 地理座標から平面座標へ自動変換

### 3. **ストリーミングパーサー（98%メモリ削減）**
- **従来**: 10GB CityGMLファイル → 20-50GBメモリ使用
- **現在**: 同じファイル → 10-100MB/建物（ビルディング単位で処理）
- **速度**: 3-5倍高速化

### 4. **マルチページレイアウト**
```python
# A4用紙に自動配置（複数ページ対応）
POST /api/step/unfold-pdf
{
  "page_format": "A4",
  "layout_mode": "single_page",  # or "multi_page"
  "scale_factor": 1.0
}
```

### 5. **面番号付け**
- 組み立てガイドとして各面に番号を自動割り当て
- SVG/PDFに視覚的に表示

---

## 🚫 **重要: 糊代（のりしろ/Assembly Tabs）について**

### 現状の事実
```python
# ALL unfold methods return:
return {
    "polygons": [...],      # ✅ 生成される
    "fold_lines": [...],    # ✅ 生成される
    "cut_lines": [...],     # ✅ 生成される
    "tabs": [],             # ❌ 常に空リスト
}
```

### **糊代は生成されていない（意図的な設計）**

#### なぜ糊代がないのか？

1. **設計哲学**:
   - Paper-CADは「フラットパターン生成器」であり、「ペーパークラフトテンプレート生成器」ではない
   - 精密な幾何学による正確な展開がコアバリュー
   - 糊代は将来の補助機能として位置づけ

2. **柔軟性**:
   ```
   【紙模型】     → 糊代が欲しい（手作業組立）
   【レーザーカット】→ 糊代不要（木工用ボンドやネジで固定）
   【CNCマシン】   → 糊代不要（別途組み立て）
   【厚紙試作】   → 糊代が欲しい（クイック組立）
   ```

3. **実装の複雑さ**:
   - 隣接面の共有エッジ検出
   - タブ形状生成（台形/矩形）
   - 衝突検出（他の面と重ならないように）
   - 折り方向判定（山折り/谷折り）

#### インフラは存在する
```python
# タブ幅パラメータ（設定可能だが未使用）
tab_width: float = 5.0  # mm

# タブ生成メソッド（スタブ実装）
def _generate_tabs_for_group(self, face_indices):
    # 簡易実装あり、だが呼ばれない
    return []

# SVGレンダリング（準備済み）
.tab-polygon {
    stroke: #0066cc;
    stroke-dasharray: 4,4;  # 青い点線
}
```

#### エージェント向けガイドライン

**糊代関連の作業依頼があった場合:**
1. ✅ 「現在は糊代生成機能は実装されていません」と説明
2. ✅ 代替案を提示:
   - 手動でInkscape/Illustratorで追加
   - 将来の実装課題として issue 化
3. ❌ 「糊代がないのはバグ」と思わない（意図的な設計）

**糊代実装を依頼された場合:**
1. プランモードで以下を調査:
   - `geometry_analyzer.py` のエッジ隣接データ
   - 既存の `_generate_tabs_for_group()` スタブ
   - 簡単なモデル（立方体、ピラミッド）でテスト戦略
2. 複雑な建物の前に平面面のみで実装

---

## 📁 重要なファイル構造

### バックエンド処理パイプライン
```
API Request (endpoints.py)
    ↓
step_processor.py (オーケストレーター)
    ↓
file_loaders.py        → STEPファイル読み込み
    ↓
geometry_analyzer.py   → 面/エッジ/隣接関係解析
    ↓
unfold_engine.py       → 3D→2D展開（スパニングツリー）
    ↓
layout_manager.py      → キャンバス/ページ配置
    ↓
svg_exporter.py        → SVG生成
pdf_exporter.py        → PDF生成（CairoSVG使用）
```

### CityGML変換（7層27モジュール）
```
citygml/pipeline/orchestrator.py  → エントリーポイント
    ├─ utils/xlink_resolver.py   → XLink参照解決
    ├─ parsers/coordinate.py     → 座標パース
    ├─ lod/extractor.py          → LOD3→2→1フォールバック
    ├─ geometry/builder.py       → ワイヤー/面/シェル/ソリッド構築
    └─ transforms/crs.py         → 座標系変換
```

### フロントエンド（npm workspace）
```
packages/
  ├─ chili-web/          → エントリーポイント
  ├─ chili-core/         → Document, Model, Material
  ├─ chili-ui/           → Web Components + CSS Modules
  ├─ chili-three/        → Three.js統合
  ├─ chili-wasm/         → WebAssembly bindings
  └─ chili-builder/      → ビルドユーティリティ
```

---

## ⚙️ 開発モード

### 通常開発 (Development)
```bash
# Frontend: localhost:8080
cd frontend && npm run dev

# Backend: localhost:8001
cd backend && conda activate paper-cad && python main.py
```

### デモモード (Demo) - 本番相当パフォーマンス
```bash
# Backend: ENV=demo python main.py
# Frontend: npm run demo
# → 本番ビルド + localhost動作 + ホットリロードなし
```

### 本番デプロイ
```bash
# Frontend: npm run deploy (Cloudflare Pages)
# Backend: Docker/Podman
```

---

## 🧪 テスト戦略

### バックエンド
```bash
pytest                              # 全テスト
pytest tests/citygml/streaming/     # ストリーミングパーサー
pytest -v                           # 詳細出力
```

### フロントエンド
```bash
npm test                            # Jest + jsdom
npm run testc                       # カバレッジレポート
```

### 手動APIテスト
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

---

## 🎨 エージェント作業時の注意点

### DO ✅
1. **ファイルを読んでから推測する**
   - ユーザーがファイル言及 → まず Read で確認
   - 根拠のある回答をする（幻覚を避ける）

2. **既存コードを編集優先**
   - 新規ファイル作成は最小限に
   - 既存パターンに従う

3. **セキュリティ意識**
   - OWASP Top 10脆弱性（XSS, SQLi, Command Injection）を避ける
   - 不安全なコードを見つけたら即座に修正

4. **シンプルさ優先**
   - 3行の重複 > 早すぎる抽象化
   - 必要最小限の複雑性
   - 仮想的な将来要件のための設計をしない

### DON'T ❌
1. **過剰エンジニアリング**
   - ❌ リクエスト外の機能追加
   - ❌ 不要なリファクタリング
   - ❌ 変更していないコードへのdocstring追加
   - ❌ 起こり得ないシナリオのエラーハンドリング

2. **後方互換性ハック**
   - ❌ 未使用変数の `_vars` へのリネーム
   - ❌ 削除コードの `// removed` コメント
   - → 使われていないものは完全削除

3. **ドキュメント乱立**
   - ❌ README.md を勝手に作成
   - ❌ ユーザー未要求のマークダウンファイル
   - → 明示的に依頼された場合のみ作成

---

## 🚀 将来ビジョン（ロードマップから）

1. **複雑形状サポート強化** - より複雑な建物形状の展開精度向上
2. **テクスチャマッピング** - 写真や色を展開図に反映（部分実装済み）
3. **バッチ処理** - 複数建物の一括変換
4. **組立説明書自動生成** - ステップバイステップガイド
5. **AR組立ガイド** - 物理とデジタルの融合
6. **コラボレーション機能** - チーム作業サポート

---

## 📜 ライセンス・コミュニティ

- **ライセンス**: AGPL-3.0（オープンソース）
- **支援**: 未踏ジュニア2025
- **哲学**: 技術工芸の民主化（Democratizing Technical Craftsmanship）

---

## 🎓 まとめ - エージェントが覚えておくべき3つのこと

1. **目的**: 手作業の展開設計を自動化し、模型制作のハードルを下げる
2. **糊代**: 現在は生成されない（意図的） - フラットパターン生成器として柔軟性を保つ
3. **原則**: Unix哲学 "Less is More" - シンプルで正確、保守可能なコードを書く

---

*このドキュメントは、様々なエージェント（Explore/Plan/一般目的）が Paper-CAD プロジェクトを理解し、適切な判断を下すための共通コンテキストです。*
