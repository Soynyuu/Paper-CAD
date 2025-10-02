# 面の隣接判定とグループ化の修正

## 問題の概要

### Issue #1: 重心ベースの隣接判定の失敗
元の実装では、2つの面が隣接しているかを**重心（centroid）間の距離**で判定していました。

```python
# 旧コード（問題あり）
centroid1 = np.array(face1["centroid"])
centroid2 = np.array(face2["centroid"])
distance = np.linalg.norm(centroid1 - centroid2)
return distance < threshold  # 立方体では常にdistance≈0になる！
```

**問題点**: 立方体のような形状では、すべての面の重心がモデルの中心付近にあるため、**距離がほぼ0になり、すべての面が「隣接」と誤判定**されていました。

### Issue #2: 過度に緩い法線判定
`_collect_adjacent_planes` 関数で：
- `allow_different_normals=True` （デフォルト）→ **すべての隣接面を無条件でグループ化**
- `threshold=0.7` → **73度までの角度差を許容**

これにより、立方体の6面（それぞれ90度で交わる）がすべて1つのグループにまとめられていました。

## 修正内容

### 1. エッジ共有ベースの隣接判定 (`_are_faces_adjacent`)

**新しいアプローチ**:
- 2つの面の**境界線の頂点を比較**
- **2つ以上の頂点を共有**していれば、エッジを共有している = 隣接している
- 数値許容誤差 0.01mm で頂点マッチング

```python
# 新コード（修正版）
vertices1 = [面1の全頂点]
vertices2 = [面2の全頂点]

shared_vertices = []
for v1 in vertices1:
    for v2 in vertices2:
        if distance(v1, v2) < 0.01mm:
            shared_vertices.append(v1)

# 2つ以上の頂点を共有 = エッジを共有
return len(shared_vertices) >= 2
```

### 2. 同一平面のみをグループ化 (`_collect_adjacent_planes`)

**変更点**:
- `allow_different_normals=False` （デフォルト変更）
- `threshold=0.05` → **約18度以内の面のみをグループ化**

これにより：
- ✓ 同一平面または非常に近い角度の面のみがグループ化される
- ✓ 立方体では各面が個別にグループ化される（6面 → 6グループ）
- ✓ ペーパークラフトとして組み立て可能な展開図が生成される

## 期待される動作

### 立方体（6面）の場合
**修正前**:
```
グループ1: [0, 1, 2, 3, 4, 5]  ← すべての面が1グループ（誤り）
```

**修正後**:
```
グループ1: [0]  ← 上面
グループ2: [1]  ← 下面
グループ3: [2]  ← 前面
グループ4: [3]  ← 背面
グループ5: [4]  ← 右面
グループ6: [5]  ← 左面
```

### 複雑な形状の場合
- 同一平面上の複数の面 → 1つのグループにまとめられる
- 異なる角度の面 → 個別のグループ

## テスト方法

1. バックエンドサーバーを起動
2. 立方体または家型のSTEPファイルを読み込み
3. 展開処理を実行
4. ログで以下を確認：
   - `共有頂点数=N` が適切な値（隣接面で2以上、非隣接面で0-1）
   - グループ数が適切（立方体で6グループ）

## 修正したファイル

- `/Users/kodaimiyazaki/devel/Paper-CAD/backend/core/unfold_engine.py`
  - `_are_faces_adjacent` メソッド（全面書き換え）
  - `_collect_adjacent_planes` メソッド（パラメータとロジック修正）
