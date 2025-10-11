# PLATEAU Auto-Fetch Feature

自動的にPLATEAUのCityGMLデータを住所や施設名から取得してインポートする機能の使用方法。

## 概要 / Overview

住所や施設名を入力するだけで、PLATEAUの建物データを自動的に取得・変換してインポートできます。CityGMLファイルを手動でダウンロードする必要はありません。

Simply enter an address or facility name to automatically fetch, convert, and import PLATEAU building data. No need to manually download CityGML files.

## 使い方 / How to Use

### フロントエンド / Frontend

1. **コマンドの実行**
   - リボンメニューから「ファイル」→「住所からインポート」を選択
   - または、コマンドパレットから `Import from Address` を実行

2. **パラメータ設定**
   - **住所または施設名** (`searchQuery`):
     - 例: `"東京駅"`, `"東京都千代田区丸の内1-9-1"`, `"渋谷スクランブルスクエア"`
   - **検索半径** (`searchRadius`):
     - デフォルト: `0.001` (約100m)
     - 単位: 度（degrees）
   - **建物数** (`buildingLimit`):
     - デフォルト: `1` (最近傍の1棟のみ)
     - 複数指定可能
   - **自動再投影** (`autoReproject`):
     - デフォルト: `true`
     - PLATEAU座標系を自動的に適切な座標系に変換

3. **実行結果**
   - 自動的に座標検索→CityGML取得→STEP変換→インポートが実行されます
   - 成功すると、建物IDと距離が表示されます

### バックエンドAPI / Backend API

#### 1. 建物検索 / Search Buildings

```http
POST /api/plateau/search-by-address
Content-Type: application/json

{
  "query": "東京駅",
  "radius": 0.001,
  "limit": 10,
  "auto_select_nearest": true
}
```

**レスポンス例:**
```json
{
  "success": true,
  "geocoding": {
    "query": "東京駅",
    "latitude": 35.681236,
    "longitude": 139.767125,
    "display_name": "東京駅, 千代田区, 東京都, 日本",
    "osm_type": "way",
    "osm_id": 123456789
  },
  "buildings": [
    {
      "building_id": "13101-bldg-123456",
      "gml_id": "BLD_abc123",
      "latitude": 35.681236,
      "longitude": 139.767125,
      "distance_meters": 15.3,
      "height": 45.0,
      "usage": "業務施設",
      "measured_height": 45.0
    }
  ],
  "found_count": 1,
  "error": null
}
```

#### 2. ワンステップ変換 / One-Step Conversion

```http
POST /api/plateau/fetch-and-convert
Content-Type: multipart/form-data

query: 東京駅
radius: 0.001
building_limit: 1
auto_reproject: true
method: solid
```

**レスポンス:** STEPファイル (application/octet-stream)

## 技術詳細 / Technical Details

### 使用API / APIs Used

1. **OpenStreetMap Nominatim API**
   - エンドポイント: `https://nominatim.openstreetmap.org/search`
   - 用途: 住所・施設名→座標変換
   - レート制限: **1リクエスト/秒** (厳密に遵守)
   - 無料・登録不要

2. **PLATEAU Data Catalog API**
   - エンドポイント: `https://api.plateauview.mlit.go.jp/datacatalog/citygml/`
   - 用途: 座標範囲指定でCityGML取得
   - フォーマット: `r:lon1,lat1,lon2,lat2` (経度が先!)
   - 無料・登録不要

### 処理フロー / Process Flow

```
ユーザー入力: "東京駅"
  ↓
[1] Nominatim API
  → 座標取得: (35.681236, 139.767125)
  ↓
[2] PLATEAU Data Catalog API
  → CityGML XML取得 (±100m範囲)
  ↓
[3] XMLパース
  → 建物情報抽出 (建物ID, gml:id, 座標, 高さ, 用途)
  ↓
[4] 最近傍検索
  → shapely.geometry.Pointで距離計算
  ↓
[5] 既存の export_step_from_citygml()
  → building_idsフィルタで該当建物のみ変換
  ↓
[6] STEPファイル返却
  ↓
インポート完了!
```

### 建物ID優先度 / Building ID Priority

PLATEAU CityGMLには2種類のIDがあります：

1. **建物ID（優先）** - `gen:genericAttribute[@name='建物ID']`
   - 形式: `13101-bldg-123456` (市区町村コード-bldg-連番)
   - 物理的な建物に紐づく安定したID
   - PLATEAU更新後も同じ建物には同じIDが維持される
   - **推奨**

2. **gml:id（フォールバック）** - `Building`要素の`gml:id`属性
   - 形式: `BLD_uuid`
   - XMLファイル内での技術的な識別子
   - PLATEAU更新で変わる可能性がある
   - 建物IDが取得できない場合のフォールバック

### エラーハンドリング / Error Handling

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `Address not found` | 住所が見つからない | 住所の書き方を変更する (例: "東京駅"→"東京都千代田区丸の内") |
| `No buildings found` | 指定範囲にPLATEAUデータなし | 検索半径を広げる、または別の場所を試す |
| `PLATEAU API timeout` | PLATEAU APIがタイムアウト | 時間をおいて再試行 |
| `Rate limit exceeded` | Nominatimリクエスト過多 | 1秒以上待ってから再試行 |

## セットアップ / Setup

### バックエンド依存関係 / Backend Dependencies

```bash
# Condaでインストール
conda env update -f backend/environment.yml

# または個別にインストール
conda install -c conda-forge geopy=2.4.1
conda install -c conda-forge shapely=2.0.7
conda install -c conda-forge requests
```

**必須パッケージ:**
- `geopy`: 住所→座標変換
- `shapely`: 距離計算
- `requests`: HTTP通信 (標準)

### フロントエンド依存関係 / Frontend Dependencies

すべて標準ブラウザAPIを使用しているため、追加の依存関係は不要です。

## 制限事項 / Limitations

1. **Nominatim APIレート制限**
   - 1秒に1リクエストまで（厳守）
   - ユーザーエージェント必須
   - 詳細: [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)

2. **PLATEAU カバレッジ**
   - PLATEAUがカバーしている地域のみ対応
   - 主要都市部が中心（詳細: [PLATEAU公式サイト](https://www.mlit.go.jp/plateau/)）

3. **座標精度**
   - 住所の曖昧さによっては正確な座標が取得できない場合がある
   - 施設名の方が精度が高い傾向

## トラブルシューティング / Troubleshooting

### Q: 建物が見つからない

**A:** 以下を確認してください:
1. PLATEAU範囲内の住所か？ → [PLATEAU提供地域](https://www.mlit.go.jp/plateau/)で確認
2. 住所の書き方は適切か？ → 「東京駅」「東京都千代田区丸の内」など複数試す
3. 検索半径は十分か？ → `searchRadius`を`0.002`や`0.005`に拡大

### Q: APIがタイムアウトする

**A:** 以下を試してください:
1. ネットワーク接続を確認
2. PLATEAUサーバーの状態を確認
3. 時間をおいて再試行
4. `building_limit`を減らして負荷軽減

### Q: Nominatimから座標が取得できない

**A:** 住所の書き方を変更してください:
- ❌ "丸の内" → ✅ "東京都千代田区丸の内"
- ❌ "100-0005" → ✅ "東京都千代田区丸の内1-9-1"
- 施設名を使う: "東京駅" "渋谷スクランブルスクエア"

## 例 / Examples

### 例1: 東京駅周辺の建物

```typescript
// Frontend
const result = await cityGMLService.fetchAndConvertByAddress("東京駅", {
    radius: 0.001,
    buildingLimit: 1,
    autoReproject: true,
});
```

### 例2: 渋谷スクランブルスクエア

```bash
# cURL
curl -X POST "http://localhost:8001/api/plateau/fetch-and-convert" \
  -F "query=渋谷スクランブルスクエア" \
  -F "radius=0.001" \
  -F "building_limit=1" \
  -F "auto_reproject=true" \
  -F "method=solid" \
  --output shibuya_building.step
```

### 例3: 複数建物の検索

```bash
# Search API
curl -X POST "http://localhost:8001/api/plateau/search-by-address" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "東京都千代田区丸の内",
    "radius": 0.002,
    "limit": 10
  }'
```

## 参考資料 / References

- [PLATEAU公式サイト](https://www.mlit.go.jp/plateau/)
- [PLATEAU Data Catalog](https://www.geospatial.jp/ckan/dataset/plateau)
- [OpenStreetMap Nominatim](https://nominatim.org/)
- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)
- [GitHub Issue #41](https://github.com/Soynyuu/paper-cad/issues/41)

## ライセンス / License

このプロジェクトはAGPL-3.0ライセンスの下で公開されています。

This project is licensed under the AGPL-3.0 License.
