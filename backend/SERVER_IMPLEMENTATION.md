# paper-cad サーバーサイド実装詳細

## 概要
3D STEPファイルを2Dペーパークラフト用SVGに変換するWebサービス  
2025年未踏ジュニアプロジェクト

## 動作環境

### システム要件
- **OS**: Linux/macOS/Windows (Docker対応)
- **Python**: 3.10以上
- **メモリ**: 4GB以上推奨
- **ディスク**: 2GB以上の空き容量

### 主要な依存ライブラリ
```yaml
# 必須コアライブラリ
- pythonocc-core==7.9.0  # OpenCASCADE Python バインディング
- occt==7.9.0            # OpenCASCADE Technology (CADカーネル)
- fastapi==0.116.1       # Webフレームワーク
- uvicorn==0.35.0        # ASGIサーバー

# 幾何学処理
- numpy==2.2.6           # 数値計算
- scipy==1.15.3          # 科学計算
- shapely==2.0.7         # ポリゴン交差判定
- networkx==3.4.2        # グラフアルゴリズム

# 可視化・出力
- svgwrite==1.4.3        # SVG生成
- matplotlib==3.10.3     # グラフ描画（デバッグ用）

# ユーティリティ
- pydantic==2.11.7       # データ検証
- python-dotenv==1.1.1   # 環境変数管理
- python-multipart==0.0.20 # ファイルアップロード
```

## 実装コード構成

### 1. エントリーポイント (main.py)
```python
# FastAPIアプリケーション起動
# ポート8001でHTTPサーバー起動
# アクセスログ、ヘルスチェック機能
```

### 2. APIエンドポイント (api/endpoints.py)

#### STEP→SVG変換
```
POST /api/step/unfold
パラメータ:
  - file: STEPファイル (必須)
  - return_face_numbers: 面番号データ返却 (default: True)
  - output_format: "svg" | "json" (default: "svg")
  - layout_mode: "canvas" | "paged" (default: "canvas")
  - page_format: "A4" | "A3" | "Letter" (default: "A4")
  - page_orientation: "portrait" | "landscape" (default: "portrait")
  - scale_factor: スケール倍率 (default: 10.0)
```

#### CityGML→STEP変換
```
POST /api/citygml/to-step
パラメータ:
  - file: CityGMLファイル または gml_path: ローカルパス
  - default_height: 押し出し高さ (default: 10.0)
  - limit: 処理建物数上限 (default: 5)
  - reproject_to: 出力座標系 (例: EPSG:6676)
  - auto_reproject: 自動投影変換 (default: True)
```

#### ヘルスチェック
```
GET /api/health
レスポンス: {
  "status": "healthy",
  "occt_available": true,
  "version": "1.0.0"
}
```

### 3. コア処理パイプライン

#### StepUnfoldGenerator (services/step_processor.py)
メイン処理クラス - パイプライン全体を統括

#### 処理フロー
1. **FileLoader** (core/file_loaders.py)
   - STEP/BREP形式の読み込み
   - OpenCASCADEでソリッド形状として解析

2. **GeometryAnalyzer** (core/geometry_analyzer.py)
   - 面分類: 平面、円筒面、円錐面
   - エッジ情報の抽出
   - 法線ベクトル計算

3. **UnfoldEngine** (core/unfold_engine.py)
   - 3D→2D展開アルゴリズム
   - 平面展開、円筒展開、円錐展開
   - 隣接面グループ化

4. **LayoutManager** (core/layout_manager.py)
   - 展開図配置最適化
   - Canvas/Paged モード切り替え
   - A4/A3/Letter サイズ対応

5. **SVGExporter** (core/svg_exporter.py)
   - SVG形式で出力
   - 折り線/切り線/タブ描画
   - 面番号配置

## Condaについて

### Condaとは
Condaは科学計算向けのパッケージ管理システムで、Pythonパッケージと**ネイティブライブラリ**（C++製のOpenCASCADE等）を統合管理できます。本プロジェクトでは、OpenCASCADE Technology (OCCT) のような複雑な依存関係を持つCADライブラリを確実にインストールするために**Condaが必須**です。

### Condaのインストール
```bash
# Miniforge (推奨: conda-forgeがデフォルト)
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh

# または Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# macOSの場合
brew install miniforge  # または brew install miniconda
```

### なぜCondaが必要か
- **pythonocc-core**: OpenCASCADEのPythonバインディングは、pipでは正しくインストールできません
- **OCCT 7.9.0**: 700MB超の大規模C++ライブラリで、conda-forgeチャンネルから取得
- **依存関係の自動解決**: VTK, Qt6, FFmpeg等の複雑な依存関係を自動管理

## デプロイ方法

## A. Podmanを使わない場合

### 方法1: ローカル環境でConda使用（開発推奨）
```bash
# 1. Condaインストール確認
conda --version  # 未インストールなら上記「Condaのインストール」参照

# 2. リポジトリクローン
git clone https://github.com/soynyuu/paper-cad
cd paper-cad

# 3. Conda環境作成（初回のみ、約10-15分）
conda env create -f environment.yml

# 4. 環境有効化
conda activate paper-cad

# 5. 環境確認
python -c "import OCC; print('OpenCASCADE OK')"  # エラーが出なければ成功

# 6. サーバー起動
python main.py  # http://localhost:8001 で起動

# 7. 終了時は環境を無効化
conda deactivate
```

#### Conda環境の管理
```bash
# 環境一覧表示
conda env list

# 環境更新（environment.ymlが更新された場合）
conda env update -f environment.yml

# 環境削除（クリーンインストールしたい場合）
conda env remove -n paper-cad

# パッケージ一覧確認
conda list -n paper-cad | grep pythonocc
```

### 方法2: Docker使用（Conda環境込み）
```bash
# 1. Dockerイメージビルド（Conda環境を内包）
docker build -t paper-cad .

# 2. コンテナ起動
docker run -d -p 8001:8001 --name unfold-app paper-cad

# 3. ログ確認
docker logs -f unfold-app

# 4. 停止
docker stop unfold-app
docker rm unfold-app
```

### 方法3: Docker Compose使用（推奨）
```bash
# 1. 起動（ビルド含む）
docker-compose up -d

# 2. ログ確認
docker-compose logs -f

# 3. 再起動
docker-compose restart

# 4. 停止・削除
docker-compose down
```

## B. Podmanを使う場合（Red Hat系Linux）

### Podmanとは
Dockerの代替となるコンテナ実行環境で、デーモンレスで動作し、rootless実行が可能です。Red Hat Enterprise Linux、Fedora、CentOS Stream等で推奨されています。

### Podman環境のセットアップ
```bash
# RHEL/Rocky Linux/AlmaLinux
sudo dnf install podman podman-compose

# 確認
podman --version
```

### 方法1: Podmanデプロイスクリプト使用（最も簡単）
```bash
# 1. リポジトリクローン
git clone https://github.com/soynyuu/paper-cad
cd paper-cad

# 2. 実行権限付与
chmod +x podman-deploy.sh

# 3. ビルドと起動を一括実行
./podman-deploy.sh build-run

# その他のコマンド
./podman-deploy.sh build     # ビルドのみ
./podman-deploy.sh run       # 起動のみ
./podman-deploy.sh stop      # 停止
./podman-deploy.sh logs      # ログ表示
./podman-deploy.sh status    # ステータス確認
./podman-deploy.sh clean     # 完全削除
```

### 方法2: Podman手動実行
```bash
# 1. イメージビルド
podman build -t paper-cad .

# 2. コンテナ作成・起動
podman run -d \
  --name unfold-app \
  -p 8001:8001 \
  -v ./core/debug_files:/app/core/debug_files:Z \
  paper-cad

# 3. ログ確認
podman logs -f unfold-app

# 4. 停止・削除
podman stop unfold-app
podman rm unfold-app
```

### 方法3: Podman Composeを使用
```bash
# 1. podman-compose インストール
pip install podman-compose

# 2. 起動
podman-compose up -d

# 3. ログ確認
podman-compose logs -f

# 4. 停止
podman-compose down
```

### Podman Systemdサービス化（本番環境）
```bash
# 1. サービスファイル生成
podman generate systemd --new --name unfold-app > ~/.config/systemd/user/paper-cad.service

# 2. サービス有効化
systemctl --user enable paper-cad.service
systemctl --user start paper-cad.service

# 3. 状態確認
systemctl --user status paper-cad.service
```

## 環境変数設定

### 開発環境 (.env.development)
```env
PORT=8001
FRONTEND_URL=http://localhost:3001
CORS_ALLOW_ALL=true
```

### 本番環境 (.env.production)
```env
PORT=8001
FRONTEND_URL=https://your-domain.com
CORS_ALLOW_ALL=false
```

## 動作確認

### ヘルスチェック
```bash
curl http://localhost:8001/api/health
```

### STEP→SVG変換テスト
```bash
# サンプルファイルで変換
curl -X POST \
  -F "file=@samples/sample.step" \
  http://localhost:8001/api/step/unfold \
  -o output.svg

# JSONレスポンスで取得
curl -X POST \
  -F "file=@samples/sample.step" \
  -F "output_format=json" \
  -F "return_face_numbers=true" \
  http://localhost:8001/api/step/unfold | jq .
```

### レイアウトモードテスト
```bash
# Canvasモード（単一キャンバス）
curl -X POST \
  -F "file=@test.step" \
  -F "layout_mode=canvas" \
  http://localhost:8001/api/step/unfold \
  -o canvas.svg

# Pagedモード（A4縦）
curl -X POST \
  -F "file=@test.step" \
  -F "layout_mode=paged" \
  -F "page_format=A4" \
  -F "page_orientation=portrait" \
  http://localhost:8001/api/step/unfold \
  -o paged_a4.svg
```

## システムアーキテクチャ

```
Client → FastAPI → StepUnfoldGenerator
                            ↓
        [1.FileLoader] → [2.GeometryAnalyzer] → [3.UnfoldEngine]
                                                        ↓
                         [5.SVGExporter] ← [4.LayoutManager]
                                ↓
                            SVG/JSON

基盤: OpenCASCADE Technology (OCCT) 7.9.0
```

## デバッグ機能

### デバッグファイル
処理失敗時、`core/debug_files/` にデバッグファイル自動保存:
- `debug_YYYYMMDD-HHMMSS_<tempfile>.step`

### ログ出力
```python
# アクセスログ例
[ACCESS] 127.0.0.1:54321 POST /api/step/unfold -> 200 1234.5ms
[UPLOAD] /api/step/unfold: received 65432 bytes -> /tmp/uuid.step
```

## トラブルシューティング

### OpenCASCADE未インストール
```bash
# エラー: OpenCASCADE Technology が利用できません
# 解決方法:
conda install -c conda-forge pythonocc-core=7.9.0
```

### メモリ不足
```bash
# 大規模モデルで処理失敗
# 解決方法: Dockerメモリ増加
docker run -m 8g paper-cad
```

### CORS エラー
```bash
# フロントエンドからアクセス不可
# 解決方法: 環境変数設定
FRONTEND_URL=http://your-frontend:3000
CORS_ALLOW_ALL=false  # 本番環境
```

## パフォーマンス

### 処理速度目安
- 小規模モデル (〜50面): 1-2秒
- 中規模モデル (〜200面): 3-5秒
- 大規模モデル (〜500面): 5-10秒

### 最適化ポイント
1. OpenCASCADE メッシュ生成精度調整
2. SVG出力時の小数点精度調整
3. レイアウト最適化アルゴリズム選択

## セキュリティ

### ファイルアップロード
- 最大サイズ: 100MB (設定可能)
- 許可拡張子: .step, .stp, .gml, .xml
- 一時ファイル自動削除

### API保護
- CORS設定で許可オリジン制限
- Rate limiting推奨 (Nginx/Cloudflare)
- HTTPSでの運用推奨

## ライセンス

MIT License

## サポート

Issues: https://github.com/soynyuu/paper-cad/issues
Documentation: https://github.com/soynyuu/paper-cad/blob/main/readme.md　