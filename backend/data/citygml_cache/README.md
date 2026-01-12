# CityGML Cache Directory

このディレクトリは東京23区のPLATEAU CityGMLデータをキャッシュするために使用されます。

## セットアップ

キャッシュを有効にするには、以下の手順に従ってください:

1. **tokyo23_datasets.json を準備**
   - プロジェクトルートに `tokyo23_datasets.json` を配置
   - このファイルには23区のデータセット情報（URL、エリアコードなど）が含まれます

2. **セットアップスクリプトを実行**
   ```bash
   cd backend
   python scripts/setup_citygml_cache.py --datasets-json tokyo23_datasets.json
   ```
   - 初回実行時: 30-60分（ネットワーク環境に依存）
   - 必要なディスク容量: 5GB以上
   - ダウンロードされるデータ: 約2-3GB（展開後）

3. **環境変数を設定**
   `backend/.env.development` に以下を追加:
   ```bash
   CITYGML_CACHE_ENABLED=true
   CITYGML_CACHE_DIR=backend/data/citygml_cache
   ```

4. **バックエンドを再起動**
   ```bash
   python main.py
   ```
   起動ログに `[CACHE] Loaded mesh index with XXX entries` が表示されればキャッシュが有効です

## ディレクトリ構造

セットアップ後、以下の構造になります:

```
backend/data/citygml_cache/
├── metadata.json                    # グローバルメタデータ
├── mesh_to_ward_index.json         # メッシュコード→区のマッピング（高速検索用）
├── 13101_千代田区/
│   ├── ward_metadata.json          # 区別メタデータ
│   └── udx/bldg/*.gml              # CityGMLファイル
├── 13102_中央区/
│   ├── ward_metadata.json
│   └── udx/bldg/*.gml
...
└── 13123_江戸川区/
    ├── ward_metadata.json
    └── udx/bldg/*.gml
```

## メンテナンス

PLATEAUの新しいデータがリリースされたとき（通常年1回）:

```bash
# 既存キャッシュを削除
rm -rf backend/data/citygml_cache/*

# 最新のtokyo23_datasets.jsonを準備

# セットアップスクリプトを再実行
python scripts/setup_citygml_cache.py --datasets-json tokyo23_datasets.json
```

## トラブルシューティング

- **ディスク容量不足**: `df -h` でディスク容量を確認し、5GB以上の空き容量を確保してください
- **ダウンロードエラー**: ネットワーク接続を確認し、`--skip-existing` オプションでレジュームしてください
- **キャッシュミス**: メッシュコードが東京23区外の場合、自動的にAPIフォールバックします

詳細な情報は `README.md` の "CityGML Cache Setup" セクションを参照してください。
