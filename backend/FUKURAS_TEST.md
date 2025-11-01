# 渋谷フクラス検索機能のテスト手順

## 概要
渋谷フクラスの検索をハードコーディングで対応する機能のテスト手順です。

## テスト環境のセットアップ

1. **バックエンドの起動**
```bash
cd backend
conda activate paper-cad
python main.py
```

バックエンドが http://localhost:8001 で起動します。

## テストケース

### 1. 完全一致（日本語）
```bash
curl -X POST http://localhost:8001/api/plateau/search-by-address \
  -H "Content-Type: application/json" \
  -d '{
    "query": "渋谷フクラス",
    "radius": 0.001,
    "limit": 5,
    "search_mode": "hybrid"
  }'
```

**期待される結果:**
- `success: true`
- `buildings[0].name`: "渋谷フクラス"
- `buildings[0].gml_id`: "bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674"
- `buildings[0].match_reason`: "完全一致"
- `geocoding.display_name`: "渋谷フクラス (Shibuya Fukuras)..."
- `geocoding.osm_type`: "hardcoded"

### 2. 部分一致（日本語）
```bash
curl -X POST http://localhost:8001/api/plateau/search-by-address \
  -H "Content-Type: application/json" \
  -d '{
    "query": "フクラス",
    "radius": 0.001,
    "limit": 5,
    "search_mode": "hybrid"
  }'
```

**期待される結果:**
- 同上（渋谷フクラスが検索される）

### 3. 英語表記
```bash
curl -X POST http://localhost:8001/api/plateau/search-by-address \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Shibuya Fukuras",
    "radius": 0.001,
    "limit": 5,
    "search_mode": "hybrid"
  }'
```

**期待される結果:**
- 同上（渋谷フクラスが検索される）

### 4. 大文字小文字の区別なし
```bash
curl -X POST http://localhost:8001/api/plateau/search-by-address \
  -H "Content-Type: application/json" \
  -d '{
    "query": "FUKURAS",
    "radius": 0.001,
    "limit": 5,
    "search_mode": "hybrid"
  }'
```

**期待される結果:**
- 同上（渋谷フクラスが検索される）

### 5. フォールバックテスト（他の検索クエリ）
```bash
curl -X POST http://localhost:8001/api/plateau/search-by-address \
  -H "Content-Type: application/json" \
  -d '{
    "query": "東京駅",
    "radius": 0.001,
    "limit": 5,
    "search_mode": "hybrid"
  }'
```

**期待される結果:**
- 通常の検索フローが動作（ハードコーディングの影響なし）
- 東京駅付近の建物が検索される

## 確認事項

### ログ出力
バックエンドのコンソールログで以下が表示されることを確認：

```
============================================================
[SEARCH] Detected Shibuya Fukuras query - using hardcoded mesh/building ID
[SEARCH] Mesh code: 53393586, Building ID: bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674
============================================================

============================================================
[BUILDING SEARCH] Building ID: bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674, Mesh Code: 53393586
============================================================

...

============================================================
[SEARCH] Success: Found Shibuya Fukuras (hardcoded)
[SEARCH] Building ID: bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674
============================================================
```

### レスポンス構造
```json
{
  "success": true,
  "geocoding": {
    "query": "渋谷フクラス",
    "latitude": 35.65806,
    "longitude": 139.70028,
    "display_name": "渋谷フクラス (Shibuya Fukuras), 2-chōme-24-12 Dōgenzaka, Shibuya City, Tokyo",
    "osm_type": "hardcoded",
    "osm_id": 0
  },
  "buildings": [
    {
      "building_id": "...",
      "gml_id": "bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674",
      "latitude": 35.65806,
      "longitude": 139.70028,
      "distance_meters": 0.0,
      "height": ...,
      "name": "渋谷フクラス",
      "relevance_score": 1.0,
      "name_similarity": 1.0,
      "match_reason": "完全一致",
      "has_lod2": true,
      "has_lod3": ...
    }
  ],
  "found_count": 1,
  "search_mode": "hybrid",
  "error": null
}
```

## 統合テスト（Frontend）

フロントエンドから以下の手順で検索：

1. http://localhost:8080 にアクセス
2. PLATEAU検索機能を開く
3. 検索バーに「渋谷フクラス」と入力
4. 検索結果に渋谷フクラスが表示されることを確認
5. 3Dモデルが正しく読み込まれることを確認
6. 展開図が正しく生成されることを確認

## トラブルシューティング

### エラー: "Failed to fetch PLATEAU data"
- インターネット接続を確認
- PLATEAU APIが利用可能か確認（https://api.plateauview.mlit.go.jp/datacatalog/）
- メッシュコード 53393586 のデータが存在するか確認

### エラー: "No buildings found in mesh area"
- CityGMLデータの構造が変更された可能性
- Building ID が変更された可能性
- `parse_buildings_from_citygml()` 関数の動作を確認

### フォールバックが動作する場合
- ログに "WARNING: Hardcoded search failed, falling back to normal search" が表示される
- この場合、通常の検索フローで渋谷フクラスが見つかる可能性あり
- ハードコーディングのロジックに問題がある可能性

## 実装の詳細

### 変更ファイル
- `backend/services/plateau_fetcher.py` (lines 1082-1136)

### マッチング条件
- クエリに「フクラス」が含まれる（大文字小文字区別なし、日本語）
- クエリに「fukuras」が含まれる（大文字小文字区別なし、英語）

### データソース
- **メッシュコード**: 53393586（PLATEAU 3次メッシュ、1km²エリア）
- **ビルディングID**: bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674
- **座標**: 緯度 35.65806, 経度 139.70028
- **住所**: 東京都渋谷区道玄坂2-24-12

### 使用する既存関数
- `search_building_by_id_and_mesh()`: メッシュコードとビルディングIDから建物を検索
- `fetch_citygml_by_mesh_code()`: PLATEAU APIからCityGMLデータを取得
- `parse_buildings_from_citygml()`: CityGMLから建物情報を抽出
