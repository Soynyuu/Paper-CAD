# Paper-CAD デプロイメントガイド

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
  - 本番URL: https://paper-cad.soynyuu.com, https://app.paper-cad.soynyuu.com

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
# Wrangler CLIのインストール (グローバル)
npm install -g wrangler

# Cloudflareアカウントにログイン
wrangler login
```

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
   - `app.paper-cad.soynyuu.com`
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

# 環境変数をdocker-compose.ymlで直接設定するか、
# .envファイルを作成
cat > .env <<EOF
PORT=8001
FRONTEND_URL=https://app.paper-cad.soynyuu.com
CORS_ALLOW_ALL=false
EOF
```

#### 2. ビルドと起動

```bash
cd backend

# ビルドと起動
docker compose up -d --build

# ログの確認
docker compose logs -f

# 停止
docker compose down
```

#### 3. Nginxリバースプロキシとセットで起動

```bash
cd backend

# Nginxを含めて起動
docker compose --profile with-nginx up -d --build
```

### B. Podman (Rootless) を使ったデプロイ

Rocky LinuxなどのRHEL系OSでPodmanを使った本番デプロイに推奨です。

#### 1. Podmanのインストール

```bash
# Rocky Linux / RHEL / Fedora
sudo dnf install -y podman podman-compose
```

#### 2. デプロイスクリプトの実行

```bash
cd backend

# ビルドと起動 (一括実行)
bash podman-deploy.sh build-run

# または個別に実行
bash podman-deploy.sh build
bash podman-deploy.sh run
```

#### 3. コンテナの管理

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

#### 4. Systemdサービスとして登録 (推奨)

本番環境では、コンテナをSystemdサービスとして登録することで、自動起動や管理が容易になります:

```bash
cd backend

# Systemdサービスファイルを生成
bash podman-deploy.sh systemd

# サービスファイルをシステムにインストール
sudo cp container-paper-cad.service /etc/systemd/system/

# サービスを有効化して起動
sudo systemctl daemon-reload
sudo systemctl enable container-paper-cad.service
sudo systemctl start container-paper-cad.service

# ステータス確認
sudo systemctl status container-paper-cad.service

# ログの確認
sudo journalctl -u container-paper-cad.service -f
```

---

## 環境変数の設定

### フロントエンド環境変数

フロントエンドの環境変数は `frontend/.env.production` または `frontend/.env.development` に設定します:

| 変数名 | 説明 | デフォルト値 | 例 |
|--------|------|-------------|-----|
| `STEP_UNFOLD_API_URL` | バックエンドAPIのベースURL | `https://backend-paper-cad.soynyuu.com/api` | `http://localhost:8001/api` (開発環境) |
| `STEP_UNFOLD_WS_URL` | WebSocketのURL (オプション) | `null` | `wss://backend-paper-cad.soynyuu.com/ws/preview` |

**注意**: 環境変数はビルド時に `rspack.config.js` によって読み込まれ、`__APP_CONFIG__` としてバンドルに埋め込まれます。

### バックエンド環境変数

バックエンドの環境変数は `docker-compose.yml` または Podman実行時の `-e` オプションで設定します:

| 変数名 | 説明 | デフォルト値 | 例 |
|--------|------|-------------|-----|
| `PORT` | APIサーバーのポート番号 | `8001` | `8001` |
| `FRONTEND_URL` | フロントエンドのオリジンURL (CORS設定) | `http://localhost:3001` | `https://app.paper-cad.soynyuu.com` |
| `CORS_ALLOW_ALL` | すべてのオリジンを許可するか (開発環境のみ) | `false` | `true` (開発環境), `false` (本番環境) |
| `PYTHONUNBUFFERED` | Pythonの出力バッファリングを無効化 | - | `1` |

**セキュリティ上の注意**:
- 本番環境では必ず `CORS_ALLOW_ALL=false` に設定してください
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
sudo systemctl reload nginx
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
  "occt_available": true
}
```

### 2. フロントエンドの動作確認

ブラウザで以下のURLにアクセス:
- https://paper-cad.soynyuu.com または https://app.paper-cad.soynyuu.com

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
   - `environment.yml` (Conda環境定義)
   - `Dockerfile` または `Containerfile`
3. ポート8001が他のプロセスで使用されていないか確認: `sudo lsof -i :8001`

#### OpenCASCADE (OCCT) が利用できない

**問題**: `/api/health` のレスポンスで `"occt_available": false` となる

**解決策**:
1. Conda環境が正しくビルドされているか確認
2. コンテナを再ビルド:
   ```bash
   docker compose down
   docker compose up -d --build
   ```
3. `environment.yml` に `pythonocc-core` と `occt` が含まれているか確認

#### CORS エラーが発生する

**問題**: ブラウザのコンソールに CORS エラーが表示される

**解決策**:
1. `FRONTEND_URL` 環境変数が正しく設定されているか確認
2. `backend/config.py` の `origins` リストに必要なオリジンが含まれているか確認
3. 本番環境では `CORS_ALLOW_ALL=false` に設定
4. バックエンドを再起動

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

# 新しいイメージをビルド
bash podman-deploy.sh build

# Systemdサービスファイルを再生成
bash podman-deploy.sh systemd
sudo cp container-paper-cad.service /etc/systemd/system/
sudo systemctl daemon-reload

# サービスを再起動
sudo systemctl start container-paper-cad.service
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
npm run build
npm run deploy:production
```

**バックエンドデプロイ (Docker)**:
```bash
cd backend
docker compose up -d --build
```

**バックエンドデプロイ (Podman + Systemd)**:
```bash
cd backend
bash podman-deploy.sh build-run
bash podman-deploy.sh systemd
sudo cp container-paper-cad.service /etc/systemd/system/
sudo systemctl enable --now container-paper-cad.service
```

### サポート

問題が発生した場合は、以下を確認してください:
- [CLAUDE.md](./CLAUDE.md): プロジェクト全体のドキュメント
- [README.md](./README.md): プロジェクトの概要
- バックエンドのログ、Nginxのログ
- ブラウザの開発者ツールのコンソール

それでも解決しない場合は、GitHubのIssueで報告してください。
