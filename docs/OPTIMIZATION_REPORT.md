# Paper-CAD 最適化・設計改善調査レポート

**調査日**: 2025-12-20
**観点**: Unix哲学、Less is more、早すぎる最適化の回避

---

## Executive Summary

Paper-CADは機能的には良く動作しているが、**複雑性の削減**と**重複の排除**に大きな改善余地がある。パフォーマンス最適化よりも、まず**設計のシンプル化**を優先すべき。

### 最も影響の大きい問題 (Top 3)

| 優先度 | 問題 | 影響 | 複雑さ削減効果 |
|--------|------|------|----------------|
| 1 | PLATEAUエンドポイント重複 | 800行 → 200行可能 | 高 |
| 2 | エラー処理・クリーンアップの散在 | 7箇所で同一ロジック | 高 |
| 3 | フロントエンド過分割 | 12パッケージ → 5-6で十分 | 中 |

---

## Part 1: バックエンド処理フロー

### 1.1 即座に対処すべき問題（複雑性削減）

#### PLATEAUエンドポイントの重複

**場所**: `backend/api/endpoints.py`

6つのエンドポイントが90%同じロジックを繰り返している:

```
/api/plateau/search-by-address      (lines 866-974)
/api/plateau/fetch-and-convert      (lines 995-1236)
/api/plateau/search-by-id           (lines 1272-1361)
/api/plateau/fetch-by-id            (lines 1383-1486)
/api/plateau/search-by-id-and-mesh  (lines 1521-1614)
/api/plateau/fetch-by-id-and-mesh   (lines 1636-1744)
```

**問題**: 各エンドポイントが独立して以下を実装:
1. 建物検索
2. CityGMLフェッチ
3. 一時ファイル作成
4. STEP変換
5. エラー処理
6. クリーンアップ

**改善案**: 1つの汎用コンバーターと検索インターフェース

```python
# Before: 6 endpoints × 150 lines = 900 lines
# After: 1 generic converter + 3 search strategies = ~200 lines
```

#### クリーンアップロジックの重複

**場所**: `backend/api/endpoints.py` - 7箇所で同一パターン

```python
# このパターンが7回繰り返されている (lines 32-45, 218-230, 433-439, 692-700, 722-738, 1188-1200, 1220-1236)
finally:
    if tmpdir and os.path.exists(tmpdir):
        try:
            shutil.rmtree(tmpdir)
        except Exception as e:
            print(f"[CLEANUP] Failed...")
```

**改善案**: Context Managerに統一

```python
with TemporaryDirectory() as tmpdir:
    # 処理
# 自動クリーンアップ
```

### 1.2 パフォーマンス問題（実測後に対処）

以下は**実際にボトルネックと確認されてから**対処すべき:

| 問題 | 場所 | 計算量 | 対処時期 |
|------|------|--------|----------|
| 面隣接判定のO(n²) | `unfold_engine.py:103-127` | O(n²) → O(n)可能 | 100+面で問題発生時 |
| 配置検索のグリッド走査 | `layout_manager.py:274-307` | 4,800+回/配置 | 大量グループで問題発生時 |
| 頂点マッチングのネストループ | `unfold_engine.py:1817-1831` | O(v1×v2) | プロファイル後 |

**注意**: これらは「早すぎる最適化」のリスクがある。実際のユースケースでボトルネックになっているか測定が必要。

### 1.3 Unix哲学違反

#### 1つのエンドポイントが多すぎる責務を持つ

**場所**: `backend/api/endpoints.py:462-518` (`/api/citygml/to-step`)

13個のパラメータを持ち、以下を同時に処理:
- 入力バリデーション
- ファイルハンドリング
- 座標変換
- 精度制御
- フィルタリング
- 出力生成
- クリーンアップ

**改善案**: 責務を分離

```
endpoints.py      → リクエスト受付のみ
validators/       → バリデーション
services/         → ビジネスロジック
utils/cleanup.py  → リソース管理
```

---

## Part 2: フロントエンドアーキテクチャ

### 2.1 過剰な分割（Over-modularization）

**現状**: 12パッケージ、108ファイル

| パッケージ | ファイル数 | 状態 |
|------------|-----------|------|
| chili-storage | 1 | 不要な分割 |
| chili-geo | 2 | 不要な分割 |
| chili-vis | 4 | 不要な分割 |
| chili-builder | 5 | chili-webに統合可能 |

**改善案**: 12 → 5-6パッケージに統合

```
Before:
├── chili-core (28 files)
├── chili-storage (1 file)    ← 統合
├── chili-geo (2 files)       ← 統合
├── chili-vis (4 files)       ← 統合
├── chili-builder (5 files)   ← chili-webへ
├── chili-controls (14 files)
├── chili-ui (72 files)
├── chili-three (14 files)
├── chili-wasm
├── chili-web
├── chili

After:
├── chili-core (統合後35 files)
├── chili-ui (72 files)
├── chili-three (14 files)
├── chili-wasm
├── chili-web (builder統合)
├── chili
```

**効果**: パッケージボイラープレート削減、依存関係の簡素化

### 2.2 インポート構造の問題

**場所**: `chili-ui/src/stepUnfold/stepUnfoldPanel.ts:17`

```typescript
// 問題: 直接パスインポート
import { config } from "chili-core/src/config/config";

// 改善: バレルエクスポート使用
import { config } from "chili-core";
```

### 2.3 ビルド設定の簡素化余地

**場所**: `frontend/rspack.config.js`

```javascript
// 不要なフォールバック (lines 80-87)
fallback: {
    fs: false,      // ブラウザで使わない
    crypto: false,  // ブラウザで使わない
    path: false,    // ブラウザで使わない
}
```

削除可能。

---

## Part 3: コード品質・設計パターン

### 3.1 ロギングの問題

**場所**: `backend/api/endpoints.py` 全体

**現状**: 80+ の `print()` 文が散在

```python
print(f"[CLEANUP] Removed tmpdir: {tmpdir}")
print(f"[API] Processing...")
print(f"[UPLOAD] File received...")
```

**問題**:
- 重大度レベルなし
- 構造化されていない
- demo/productionでグローバルに無効化（副作用）

**改善案**: 標準のloggingモジュール使用

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Processing %s", filename)
```

### 3.2 設定ファイルの副作用

**場所**: `backend/config.py:10-15`

```python
# インポート時にグローバル状態を変更（危険）
if ENV in ["demo", "production"]:
    builtins.print = noop_print  # グローバル副作用
```

**改善案**: 明示的な初期化関数に移動

### 3.3 エラー処理の不統一

**場所**: `backend/api/endpoints.py` 全体

```python
# パターンA (一部のエンドポイント)
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))

# パターンB (他のエンドポイント)
except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")
```

**改善案**: 統一されたエラーハンドラデコレータ

---

## Part 4: 改善優先順位

### 今すぐ対処すべき（複雑性削減）

1. **PLATEAUエンドポイント統合** - 800行削減可能
2. **クリーンアップロジック統一** - Context Manager化
3. **フロントエンドパッケージ統合** - 12 → 5-6

### 次のフェーズ（コード品質）

4. **logging導入** - print文置き換え
5. **エラー処理統一** - デコレータ化
6. **config.py副作用除去** - 明示的初期化

### 計測後に検討（パフォーマンス）

7. 面隣接判定の最適化（100+面のケースで問題発生時）
8. 配置アルゴリズム改善（大量グループ配置時）
9. 頂点マッチング最適化（複雑な建物で問題発生時）

---

## 結論

**最大の改善機会は「複雑性の削減」にある。**

- コードベースは機能的には良く動作している
- パフォーマンス最適化より先に、重複排除と責務分離を行うべき
- 新しい抽象化を追加するのではなく、既存の重複を統合すべき
- Unix哲学: 1つのことを正しく行うモジュールへ分解

**Less is more**: 12パッケージより6パッケージ、6エンドポイントより2エンドポイント+戦略パターン
