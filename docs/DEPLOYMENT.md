# Paper-CAD デプロイメントガイド
ssh rocky@153.126.191.72 ps RgpQShQWYP5Zq=sA
このドキュメントでは、Paper-CADを本番環境にデプロイする手順を説明します。

## 目次

- [概要](#概要)
- [前提条件](#前提条件)
- [フロントエンドのデプロイ (Cloudflare Pages)](#フロントエンドのデプロイ-cloudflare-pages)
- [バックエンドのデプロイ (Docker/Podman)](#バックエンドのデプロイ-dockerpodman)
- [環境変数の設定](#環境変数の設定)
- [リバースプロキシの設定 (Nginx)](#リバースプロキシの設定-nginx)
- [SSL証明書の取得と設定](#ssl証明書の取得と設定)
- [デプロイ後の動作確認](#デプロイ後の動作確認)
- [トラブルシューティング](#トラブルシューティング)
- [システム管理](#システム管理)

---

## 概要

Paper-CADは以下の2つのコンポーネントから構成されています:

- **フロントエンド**: TypeScript/WebAssemblyで実装されたWebアプリケーション
  - デプロイ先: Cloudflare Pages
  - 本番URL: https://paper-cad.soynyuu.com, https://app-paper-cad.soynyuu.com

- **バックエンド**: FastAPI (Python) + OpenCASCADEで実装されたAPIサーバー
  - デプロイ先: Docker/Podmanコンテナ
  - 本番URL: https://backend-paper-cad.soynyuu.com

## 前提条件

### フロントエンドのデプロイに必要なもの

- Node.js 18以上
- npm
- Cloudflareアカウント
- Wrangler CLI (Cloudflareの公式CLI)

### バックエンドのデプロイに必要なもの

- Docker または Podman
- (オプション) Nginx (リバースプロキシとして使用)
- 最小2GB RAM、推奨4GB以上
- 10GB以上のディスクスペース

---

## フロントエンドのデプロイ (Cloudflare Pages)

### 1. 初回セットアップ

#### Cloudflareアカウントの準備

1. [Cloudflare](https://dash.cloudflare.com/)にログイン
2. Pages セクションに移動
3. 新しいプロジェクトを作成 (プロジェクト名: `paper-cad`)

#### Wrangler CLIのインストールと認証

```bash
# Wrangler CLIのインストール (グローバル - オプション)
# 注: package.jsonに含まれているため、npx経由でも使用可能
npm install -g wrangler

# Cloudflareアカウントにログイン
npx wrangler login
```

**注**: Wranglerはグローバルインストール不要です。`npx wrangler`で実行できます。

### 2. 環境変数の設定

フロントエンドディレクトリで環境設定ファイルを作成します:

```bash
cd frontend

# 本番環境用の環境変数ファイルを作成
cat > .env.production <<EOF
# Backend API URL (本番環境)
STEP_UNFOLD_API_URL=https://backend-paper-cad.soynyuu.com/api

# (オプション) WebSocket URL
# STEP_UNFOLD_WS_URL=wss://backend-paper-cad.soynyuu.com/ws/preview
EOF
```

### 3. ビルドとデプロイ

#### 依存関係のインストール

初回または依存関係更新時に必要です:

```bash
cd frontend

# 依存関係をインストール
npm install
```

#### 開発ブランチへのデプロイ (ステージング)

```bash
cd frontend

# ビルドとステージングブランチへのデプロイ
npm run deploy:staging
```

#### 本番ブランチへのデプロイ

```bash
cd frontend

# ビルドと本番ブランチへのデプロイ
npm run deploy:production
```

#### 手動デプロイ (任意のブランチ)

```bash
cd frontend

# ビルド
npm run build

# デプロイ
npx wrangler pages deploy dist --project-name=paper-cad
```

### 4. カスタムドメインの設定

1. Cloudflare Dashboardで `paper-cad` プロジェクトを選択
2. **Custom domains** タブに移動
3. カスタムドメインを追加:
   - `paper-cad.soynyuu.com`
   - `app-paper-cad.soynyuu.com`
4. DNS設定を確認 (CNAMEレコードが自動的に設定されます)

---

## バックエンドのデプロイ (Docker/Podman)

### デプロイ方法の選択

バックエンドは以下の2つの方法でデプロイできます:

- **Docker Compose**: 開発環境やシンプルな本番環境向け
- **Podman (Rootless)**: Rocky Linux等のセキュアな本番環境向け

### A. Docker Composeを使ったデプロイ

#### 1. 環境変数の設定

```bash
cd backend

# 本番環境用の環境変数を設定
# 方法1: ENV変数を使って.env.productionを読み込む (推奨)
# .env.productionは既に存在するので、ENV=productionを設定するだけでOK

# 方法2: 環境変数を直接設定する場合は.envファイルを作成
cat > .env <<EOF
ENV=production
PORT=8001
FRONTEND_URL=https://app-paper-cad.soynyuu.com
CORS_ALLOW_ALL=false
EOF
```

**注意**: バックエンドには既に `.env.development` と `.env.production` が用意されています。
- ローカル開発: 何も設定しなければ`.env.development`が自動的に読み込まれます
- 本番環境: `ENV=production`を設定すると`.env.production`が読み込まれます

#### 2. ビルドと起動

**本番環境での起動** (ENV=productionを設定):

```bash
cd backend

# ENV=productionを指定してビルド・起動
ENV=production docker compose up -d --build

# または docker-compose.yml に環境変数を追加:
# environment:
#   - ENV=production
#   - PORT=8001

# ログの確認
docker compose logs -f

# 起動時のログで環境変数の読み込みを確認
# "[CONFIG] 環境変数を .env.production から読み込みました (ENV=production)" と表示されるはず

# 停止
docker compose down
```

**開発環境での起動** (ENV変数なし、デフォルトでdevelopment):

```bash
cd backend

# ENV変数を設定しない場合、自動的に.env.developmentが読み込まれる
docker compose up -d --build

# ログで確認
# "[CONFIG] 環境変数を .env.development から読み込みました (ENV=development)" と表示される
```

#### 3. Nginxリバースプロキシとセットで起動

```bash
cd backend

# Nginxを含めて起動
docker compose --profile with-nginx up -d --build
```

### B. Podman (Rootless) を使ったデプロイ

Rocky LinuxなどのRHEL系OSでPodmanを使った本番デプロイに推奨です。

**重要**: PodmanとDocker Composeは異なるビルドファイルを使用します：
- **Podman**: `Containerfile` + `environment-docker.yml`（軽量版、プラットフォーム非依存）
- **Docker Compose**: `Dockerfile` + `environment.yml`（フルセット版、開発環境含む）

#### 1. Podmanのインストール

```bash
# Rocky Linux / RHEL / Fedora
sudo dnf install -y podman podman-compose
```

#### 2. 必要なファイルの確認

デプロイ前に以下のファイルが存在することを確認してください（すべてリポジトリに含まれています）:

```bash
cd backend

# 必要なファイルを確認
ls -la Containerfile environment-docker.yml podman-deploy.sh
```

#### 3. デプロイスクリプトの実行

**本番環境での起動**:

```bash
cd backend

# ENV=productionを設定してビルド・起動
ENV=production bash podman-deploy.sh build-run

# または個別に実行
ENV=production bash podman-deploy.sh build
ENV=production bash podman-deploy.sh run

# コンテナ内部でENV=productionが設定され、.env.productionが読み込まれる
```

**開発環境での起動** (ENV変数なし):

```bash
cd backend

# ENV変数を設定しない場合、自動的に.env.developmentが読み込まれる
bash podman-deploy.sh build-run
```

**注意**:
- `podman-deploy.sh`は自動的に`Containerfile`と`environment-docker.yml`を使用します
- 環境変数`CONTAINERFILE`で変更可能です
- ENV変数は`podman-deploy.sh`実行時に指定する必要があります（コンテナに渡されます）

#### 4. コンテナの管理

```bash
cd backend

# ステータス確認
bash podman-deploy.sh status

# ログの確認
bash podman-deploy.sh logs

# コンテナのシェルに入る
bash podman-deploy.sh shell

# 停止
bash podman-deploy.sh stop

# 完全削除 (コンテナとイメージ)
bash podman-deploy.sh remove
```

#### 5. Systemdサービスとして登録 (推奨)

本番環境では、コンテナをSystemdサービスとして登録することで、自動起動や管理が容易になります:

```bash
cd backend

# ENV=productionを設定してSystemdサービスファイルを生成
ENV=production bash podman-deploy.sh systemd

# 生成されたサービスファイルを確認
cat container-paper-cad.service
# Environment="ENV=production" が含まれていることを確認

# サービスファイルをシステムにインストール
sudo cp container-paper-cad.service /etc/systemd/system/

# サービスを有効化して起動
sudo systemctl daemon-reload
sudo systemctl enable container-paper-cad.service
sudo systemctl start container-paper-cad.service

# ステータス確認
sudo systemctl status container-paper-cad.service

# ログの確認 (.env.production が読み込まれていることを確認)
sudo journalctl -u container-paper-cad.service -f
# "[CONFIG] 環境変数を .env.production から読み込みました (ENV=production)" と表示されるはず
```

**重要**: Systemdサービスとして登録する場合、ENV変数は`podman-deploy.sh systemd`実行時に指定した値がサービスファイルに埋め込まれます。後から変更する場合は、サービスファイルを再生成してください。

---

## 環境変数の設定

### フロントエンド環境変数

フロントエンドの環境変数は `frontend/.env.production` または `frontend/.env.development` に設定します:

| 変数名 | 説明 | デフォルト値 | 例 |
|--------|------|-------------|-----|
| `STEP_UNFOLD_API_URL` | バックエンドAPIのベースURL | `http://localhost:8001/api` | `https://backend-paper-cad.soynyuu.com/api` (本番環境) |
| `STEP_UNFOLD_WS_URL` | 将来のWebSocket拡張用 (現在未使用) | `null` | `wss://backend-paper-cad.soynyuu.com/ws/preview` |

**注意**: 環境変数はビルド時に `rspack.config.js` によって読み込まれ、`__APP_CONFIG__` としてバンドルに埋め込まれます。

### バックエンド環境変数

バックエンドの環境変数は `.env.development`/`.env.production` ファイル、`docker-compose.yml`、または Podman実行時の `-e` オプションで設定します:

| 変数名 | 説明 | デフォルト値 | 例 |
|--------|------|-------------|-----|
| `ENV` | 実行環境 (`development`/`production`) | `development` | `production` |
| `PORT` | APIサーバーのポート番号 | `8001` | `8001` |
| `FRONTEND_URL` | フロントエンドのオリジンURL (CORS設定) | `http://localhost:8080` | `https://app-paper-cad.soynyuu.com` |
| `CORS_ALLOW_ALL` | すべてのオリジンを許可するか (開発環境のみ) | `false` | `true` (開発環境), `false` (本番環境) |
| `PYTHONUNBUFFERED` | Pythonの出力バッファリングを無効化 | - | `1` |

**ENV変数の動作** (v1.1.0以降):
- `ENV=development` (デフォルト): `.env.development` → `.env` の順で読み込み
- `ENV=production`: `.env.production` → `.env` の順で読み込み
- 環境変数ファイルが見つからない場合、直接設定された環境変数を使用

**ローカル開発環境**:
- `ENV`変数を設定しない場合、自動的に`development`モードで`.env.development`が読み込まれます
- `.env.development`には`CORS_ALLOW_ALL=true`が設定されており、localhost:8080からのアクセスが許可されます

**本番環境**:
- `ENV=production`を設定すると`.env.production`が読み込まれます
- 必ず`CORS_ALLOW_ALL=false`に設定し、`FRONTEND_URL`に実際のドメインを指定してください

**セキュリティ上の注意**:
- 本番環境では必ず `ENV=production` と `CORS_ALLOW_ALL=false` を設定してください
- `FRONTEND_URL` には実際のフロントエンドのドメインを設定してください
- 追加のオリジンは `backend/config.py` の `origins` リストで設定できます

---

## リバースプロキシの設定 (Nginx)

本番環境では、NginxをリバースプロキシとしてバックエンドAPIの前段に配置することを推奨します。

### 1. Nginxのインストール

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install nginx

# Rocky Linux / RHEL / Fedora
sudo dnf install nginx
```

### 2. Nginx設定ファイルの配置

サンプル設定ファイルが `backend/nginx/paper-cad.conf` に用意されています:

```bash
# 設定ファイルをコピー
sudo cp backend/nginx/paper-cad.conf /etc/nginx/conf.d/paper-cad.conf

# 設定ファイルを編集 (ドメイン名を変更)
sudo nano /etc/nginx/conf.d/paper-cad.conf
```

**重要な設定項目**:
- `server_name`: あなたのドメイン名に変更 (例: `backend-paper-cad.soynyuu.com`)
- `client_max_body_size`: 大きなSTEPファイルのアップロードに対応するため500MBに設定
- タイムアウト設定: `proxy_read_timeout 300s` など

### 3. Nginxの起動

```bash
# 設定ファイルの構文チェック
sudo nginx -t

# Nginxを起動
sudo systemctl start nginx
sudo systemctl enable nginx

# ステータス確認
sudo systemctl status nginx
```

---

## SSL証明書の取得と設定

本番環境ではHTTPSが必須です。Let's Encryptを使った無料SSL証明書の取得方法を説明します。

### 1. Certbotのインストール

```bash
# Ubuntu / Debian
sudo apt install certbot python3-certbot-nginx

# Rocky Linux / RHEL / Fedora
sudo dnf install certbot python3-certbot-nginx
```

### 2. SSL証明書の取得

```bash
# Nginxプラグインを使った自動設定
sudo certbot --nginx -d backend-paper-cad.soynyuu.com

# または、手動で証明書のみ取得
sudo certbot certonly --nginx -d backend-paper-cad.soynyuu.com
```

### 3. Nginx設定の更新

`backend/nginx/paper-cad.conf` にはHTTPS設定のテンプレートが用意されています。
コメントアウトされているHTTPS設定を有効化してください:

```bash
sudo nano /etc/nginx/conf.d/paper-cad.conf
```

以下の部分のコメントを解除:
- HTTPS server ブロック (listen 443)
- SSL証明書のパス設定
- HTTP→HTTPSリダイレクト

### 4. Nginxの再起動

```bash
# 設定のテスト
sudo nginx -t

# 再起動
sudo systemctl reload nginxsudo systemctl reload nginx
```

### 5. 証明書の自動更新

Let's Encryptの証明書は90日間有効です。自動更新を設定します:

```bash
# 自動更新のテスト
sudo certbot renew --dry-run

# cronまたはsystemd timerで自動更新が設定されていることを確認
sudo systemctl status certbot.timer
```

---

## デプロイ後の動作確認

### 1. バックエンドのヘルスチェック

```bash
# ローカルからの確認
curl http://localhost:8001/api/health

# 外部からの確認 (Nginxを使っている場合)
curl https://backend-paper-cad.soynyuu.com/api/health
```

期待されるレスポンス:
```json
{
  "status": "healthy",
  "opencascade_available": true
}
```

### 2. フロントエンドの動作確認

ブラウザで以下のURLにアクセス:
- https://paper-cad.soynyuu.com または https://app-paper-cad.soynyuu.com

確認項目:
- ページが正常に表示されるか
- 3D表示が機能するか
- バックエンドAPIとの通信が正常か (STEPファイルのアップロードと展開図生成)

### 3. CORS設定の確認

ブラウザの開発者ツール (F12) を開き、Consoleタブで以下を確認:
- CORSエラーが発生していないか
- APIリクエストが正常に完了しているか

### 4. ログの確認

#### バックエンドログ (Docker)
```bash
docker compose logs -f paper-cad
```

#### バックエンドログ (Podman)
```bash
podman logs -f paper-cad
```

#### バックエンドログ (Systemdサービス)
```bash
sudo journalctl -u container-paper-cad.service -f
```

#### Nginxログ
```bash
sudo tail -f /var/log/nginx/paper-cad.access.log
sudo tail -f /var/log/nginx/paper-cad.error.log
```

---

## トラブルシューティング

### フロントエンド関連

#### デプロイが失敗する

**問題**: `wrangler pages deploy` でエラーが発生する

**解決策**:
1. Wranglerが最新版か確認: `npm install -g wrangler@latest`
2. 認証情報を再設定: `wrangler logout && wrangler login`
3. ビルドが正常に完了しているか確認: `npm run build`

#### バックエンドに接続できない

**問題**: フロントエンドからバックエンドAPIへの接続が失敗する

**解決策**:
1. `STEP_UNFOLD_API_URL` が正しく設定されているか確認
2. CORS設定が正しいか確認 (ブラウザのコンソールログを確認)
3. バックエンドが起動しているか確認: `curl https://backend-paper-cad.soynyuu.com/api/health`

### バックエンド関連

#### コンテナが起動しない

**問題**: Docker/Podmanコンテナが起動に失敗する

**解決策**:
1. ログを確認: `docker compose logs` または `podman logs paper-cad`
2. 必要なファイルが存在するか確認:
   - **Docker Compose**: `environment.yml` + `Dockerfile`
   - **Podman**: `environment-docker.yml` + `Containerfile`
3. ポート8001が他のプロセスで使用されていないか確認: `sudo lsof -i :8001`

#### OpenCASCADE (OCCT) が利用できない

**問題**: `/api/health` のレスポンスで `"opencascade_available": false` となる

**解決策**:
1. Conda環境が正しくビルドされているか確認
2. コンテナを再ビルド:
   ```bash
   # Docker Composeの場合
   docker compose down
   docker compose up -d --build

   # Podmanの場合
   bash podman-deploy.sh remove
   bash podman-deploy.sh build-run
   ```
3. 環境ファイル (`environment.yml` または `environment-docker.yml`) に `pythonocc-core` と `occt` が含まれているか確認

#### CORS エラーが発生する

**問題**: ブラウザのコンソールに CORS エラーが表示される

**解決策**:

1. **環境設定を確認**:
   - ローカル開発: `ENV`変数が設定されていないか、`ENV=development`になっているか確認
   - 本番環境: `ENV=production`が設定されているか確認

2. **適切な.envファイルが読み込まれているか確認**:
   ```bash
   # ログで確認
   docker compose logs | grep CONFIG
   # または
   podman logs paper-cad | grep CONFIG

   # 期待される出力:
   # [CONFIG] 環境変数を .env.development から読み込みました (ENV=development)  # 開発環境
   # [CONFIG] 環境変数を .env.production から読み込みました (ENV=production)  # 本番環境
   ```

3. **CORS設定を確認**:
   - 開発環境: `.env.development`で`CORS_ALLOW_ALL=true`が設定されているか
   - 本番環境: `.env.production`で`CORS_ALLOW_ALL=false`と`FRONTEND_URL`が正しく設定されているか

4. `backend/config.py` の `origins` リストに必要なオリジンが含まれているか確認

5. バックエンドを再起動して設定を反映

#### 大きなファイルのアップロードが失敗する

**問題**: PLATEAU等の大きなCityGML/STEPファイルのアップロードが失敗する

**解決策**:
1. Nginxの `client_max_body_size` を増やす (推奨: 500M)
2. タイムアウト設定を延長:
   - `client_body_timeout 300s`
   - `proxy_read_timeout 300s`
3. Nginx設定を再読み込み: `sudo systemctl reload nginx`

---

## システム管理

### 定期的なメンテナンス

#### ログのローテーション

Docker/Podmanのログが肥大化するのを防ぐため、`docker-compose.yml` にログローテーション設定が含まれています:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

#### ディスクスペースの確認

```bash
# Docker/Podmanのディスク使用量確認
docker system df

# 不要なイメージやコンテナの削除
docker system prune -a
```

### バックアップ

#### コンテナの設定をバックアップ

```bash
# Docker Composeの設定
cp backend/docker-compose.yml /path/to/backup/

# 環境変数ファイル (存在する場合)
cp backend/.env /path/to/backup/

# Nginx設定
sudo cp /etc/nginx/conf.d/paper-cad.conf /path/to/backup/
```

### アップデート手順

#### フロントエンドのアップデート

```bash
cd frontend

# 最新コードを取得
git pull origin main

# 依存関係を更新
npm install

# ビルドしてデプロイ
npm run deploy:production
```

#### バックエンドのアップデート (Docker)

```bash
cd backend

# 最新コードを取得
git pull origin main

# コンテナを再ビルドして再起動
docker compose down

# 本番環境
ENV=production docker compose up -d --build

# 開発環境
docker compose up -d --build
```

#### バックエンドのアップデート (Podman + Systemd)

```bash
cd backend

# 最新コードを取得
git pull origin main

# サービスを停止
sudo systemctl stop container-paper-cad.service

# コンテナを削除
podman stop paper-cad
podman rm paper-cad

# 新しいイメージをビルド (本番環境)
ENV=production bash podman-deploy.sh build

# Systemdサービスファイルを再生成 (ENV=productionを忘れずに)
ENV=production bash podman-deploy.sh systemd
sudo cp container-paper-cad.service /etc/systemd/system/
sudo systemctl daemon-reload

# サービスを再起動
sudo systemctl start container-paper-cad.service

# ログで.env.productionが読み込まれていることを確認
sudo journalctl -u container-paper-cad.service -f
```

### モニタリング

#### リソース使用量の監視

```bash
# コンテナのリソース使用量をリアルタイムで表示
docker stats paper-cad

# または Podman
podman stats paper-cad
```

#### アクセスログの監視

```bash
# Nginxアクセスログをリアルタイムで表示
sudo tail -f /var/log/nginx/paper-cad.access.log

# エラーログも同時に表示
sudo tail -f /var/log/nginx/paper-cad.access.log -f /var/log/nginx/paper-cad.error.log
```

#### ヘルスチェックの自動化

定期的にヘルスチェックを実行するcronジョブを設定:

```bash
# crontabを編集
crontab -e

# 5分ごとにヘルスチェック (失敗時はメール通知)
*/5 * * * * curl -f https://backend-paper-cad.soynyuu.com/api/health || echo "Backend health check failed" | mail -s "Paper-CAD Alert" your-email@example.com
```

---

## まとめ

このガイドに従うことで、Paper-CADを本番環境に安全かつ確実にデプロイできます。

### クイックリファレンス

**フロントエンドデプロイ**:
```bash
cd frontend
npm install  # 初回のみ
npm run build
npm run deploy:production
```

**バックエンドデプロイ (Docker Compose)**:
```bash
cd backend
# 使用ファイル: Dockerfile + environment.yml

# 本番環境
ENV=production docker compose up -d --build

# 開発環境 (ENV変数なしでdevelopmentがデフォルト)
docker compose up -d --build
```

**バックエンドデプロイ (Podman + Systemd)**:
```bash
cd backend
# 使用ファイル: Containerfile + environment-docker.yml

# 本番環境
ENV=production bash podman-deploy.sh build-run
ENV=production bash podman-deploy.sh systemd
sudo cp container-paper-cad.service /etc/systemd/system/
sudo systemctl enable --now container-paper-cad.service

# 開発環境 (ENV変数なしでdevelopmentがデフォルト)
bash podman-deploy.sh build-run
```

### サポート

問題が発生した場合は、以下を確認してください:
- [CLAUDE.md](./CLAUDE.md): プロジェクト全体のドキュメント
- [README.md](./README.md): プロジェクトの概要
- バックエンドのログ、Nginxのログ
- ブラウザの開発者ツールのコンソール

それでも解決しない場合は、GitHubのIssueで報告してください。
