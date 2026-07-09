# Local Demo Mode

Paper-CAD の `local_demo` は、会場 Wi-Fi なしで PLATEAU 建物検索、Cesium 表示、STEP インポート、展開図生成を見せるためのデモモードです。

## 対象施設

施設名検索で以下を入力できます。

- 芝浦工大附属
- JPタワー
- 渋谷フクラス

対象の建物 ID、メッシュコード、3D Tiles、CityGML、地形は `backend/data/local_demo_cache` と `backend/data/local_demo_cache/manifest.json` に同梱されています。

## 起動手順

バックエンド:

```bash
cd backend
ENV=local_demo python main.py
```

フロントエンド:

```bash
cd frontend
npm run local_demo
```

ブラウザで `http://localhost:8080` を開き、PLATEAU 建物インポートを起動します。

## 何がオフラインになるか

- 施設名検索: `manifest.json` の対象建物に固定して解決します。Nominatim や PLATEAU API へは行きません。
- 3D Tiles: `/local-demo-cache/3dtiles/...` から配信されます。
- CityGML: `/backend/data/local_demo_cache/citygml_cache` を使います。
- Cesium 本体: フロントエンドビルド時に `dist/cesium` へコピーされます。
- 地形: `CESIUM_TERRAIN_URL=http://localhost:8001/local-demo-cache/terrain` を使います。
- GSI/PLATEAU オルソ画像: `CESIUM_GSI_*_URL` と `CESIUM_PLATEAU_ORTHO_URL` のローカル URL を使います。画像タイルが未同梱の場合は、backend がニュートラルなローカルPNGを返します。
- STEP インポート: `/api/plateau/fetch-by-id-and-mesh` がローカル CityGML から変換します。
- 展開図: `/api/plateau/unfold-textured-by-id-and-mesh` がローカル CityGML から STEP と SVG を生成します。

`CESIUM_OFFLINE_MODE=true` のため、地形ロード失敗時も Cesium World Terrain へ外部フォールバックしません。

## 展開図とテクスチャ

通常の展開図生成はローカルで完結します。テクスチャ付き展開図は CityGML の `app:ParameterizedTexture` と画像ファイルが必要です。

現状の同梱キャッシュには CityGML はありますが、建物テクスチャ画像までは含めていません。そのためローカルデモでは、外部画像取得をスキップし、テクスチャなしの展開図にフォールバックします。外部 HTTP へ画像を取りに行かないようにガードしています。

テクスチャ付きデモが必要な場合は、CityGML と同じキャッシュ配下に参照画像を配置し、CityGML の `app:imageURI` から相対パスで解決できるようにしてください。

## 検証

ローカルデモ関連のバックエンドテスト:

```bash
cd backend
conda run -n paper-cad pytest tests/test_local_demo.py tests/test_local_demo_texture_mapper.py
```

フロントエンドのローカルデモビルド:

```bash
cd frontend
npm run local_demo:build
```

## キャッシュ更新

キャッシュを作り直す場合は、ネットワークがある環境で次を実行します。

```bash
cd backend
python scripts/prepare_local_demo_cache.py --validate
```

更新後は `backend/data/local_demo_cache/manifest.json` に対象3件の `building_id` と `mesh_code` が入っていることを確認してください。

## 注意点

- キャッシュ範囲外へカメラを動かすと、未保存のタイルは 404 になります。
- 対象3件以外の施設名検索は通常検索経路になるため、完全オフラインでは失敗します。
- `frontend/dist` はビルド時に clean されます。古いチャンクが残って外部 URL を参照しないようにするためです。
