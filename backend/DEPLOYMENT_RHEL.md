# RHEL系OSへのPodmanデプロイガイド

Paper-CAD バックエンドAPI（unfold-step2svg）をRHEL系OS（Rocky Linux、AlmaLinux、RHEL 9.x）にPodmanでデプロイする包括的なガイドです。

## 目次

- [システム要件](#システム要件)
- [クイックスタート](#クイックスタート)
- [詳細セットアップ手順](#詳細セットアップ手順)
- [systemdサービス化](#systemdサービス化)
- [セキュリティ設定](#セキュリティ設定)
- [プロダクション環境向け設定](#プロダクション環境向け設定)
- [トラブルシューティング](#トラブルシューティング)

---

## システム要件

### 対応OS

- **Rocky Linux** 9.x（推奨）
- **AlmaLinux** 9.x
- **RHEL** (Red Hat Enterprise Linux) 9.x
- その他RHEL系ディストリビューション

### ハードウェア要件

- **CPU**: 2コア以上推奨（4コア以上でパフォーマンス向上）
- **メモリ**: 4GB以上推奨（8GB以上が理想）
- **ディスク**: 10GB以上の空き容量
- **ネットワーク**: インターネット接続（初回ビルド時）

### ソフトウェア要件

- **Podman**: 4.0以降（RHEL 9には標準で含まれる）
- **Git**: バージョン管理用
- **curl**: ヘルスチェック用

---

## クイックスタート

最速でデプロイする手順です（podman-deploy.shスクリプト使用）。

### 1. 必要なツールのインストール

```bash
# OS確認
cat /etc/os-release

# システムパッケージの更新
sudo dnf update -y

# 必要なツールのインストール
sudo dnf install -y podman git curl

# Podmanバージョン確認（4.0以降であることを確認）
podman --version
```

### 2. リポジトリのクローン

```bash
# プロジェクトディレクトリへ移動（例: /opt/applications）
cd /opt/applications

# リポジトリをクローン
git clone https://github.com/Soynyuu/Paper-CAD.git
cd Paper-CAD/backend
```

### 3. デプロイスクリプトの実行

```bash
# ビルドと起動を一度に実行（デフォルト動作）
bash podman-deploy.sh build-run

# または段階的に実行
bash podman-deploy.sh build    # イメージビルド
bash podman-deploy.sh run      # コンテナ起動
```

### 4. 動作確認

```bash
# ヘルスチェック
curl http://localhost:8001/api/health

# 期待される応答:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "opencascade_available": true,
#   "citygml_support": true,
#   "supported_formats": ["step", "stp", "citygml", "gml"]
# }

# コンテナステータス確認
bash podman-deploy.sh status
```

---

## 詳細セットアップ手順

### Step 1: システムの準備

#### 1.1 システムパッケージの更新

```bash
sudo dnf update -y
sudo dnf install -y epel-release  # Extra Packages for Enterprise Linux
```

#### 1.2 Podmanのインストールと設定

```bash
# Podmanとpodman-composeのインストール
sudo dnf install -y podman podman-compose

# Podmanの設定確認
podman info

# rootlessモードで実行するための設定（推奨）
# サブUID/サブGIDが設定されているか確認
grep $USER /etc/subuid /etc/subgid

# 設定されていない場合は追加
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
```

#### 1.3 ファイアウォールの設定（オプション）

外部からアクセスする場合のみ必要です。

```bash
# ポート8001を開放
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --reload

# 設定確認
sudo firewall-cmd --list-ports
```

### Step 2: プロジェクトの取得

```bash
# 作業ディレクトリの作成（例: /opt/applications）
sudo mkdir -p /opt/applications
sudo chown $USER:$USER /opt/applications
cd /opt/applications

# リポジトリをクローン
git clone https://github.com/Soynyuu/Paper-CAD.git
cd Paper-CAD/backend

# ブランチ確認（mainブランチであることを確認）
git branch
```

### Step 3: コンテナイメージのビルド

#### 3.1 自動ビルド（推奨）

```bash
# podman-deploy.shを使用したビルド
bash podman-deploy.sh build
```

#### 3.2 手動ビルド

```bash
# Containerfileを使用してビルド
podman build --no-cache -f Containerfile -t unfold-step2svg:latest .

# ビルド完了確認
podman images | grep unfold-step2svg
```

**ビルド時の注意点:**
- 初回ビルドは10〜20分程度かかります（Conda環境のダウンロードとセットアップ）
- インターネット接続が必要です
- `environment-docker.yml`が使用されます（プラットフォーム非依存）

### Step 4: コンテナの起動

#### 4.1 自動起動（推奨）

```bash
# podman-deploy.shを使用した起動
bash podman-deploy.sh run
```

#### 4.2 手動起動

```bash
# debug_filesディレクトリの作成
mkdir -p core/debug_files

# コンテナ起動（rootlessモード）
podman run -d \
  --name unfold-step2svg \
  --restart always \
  -p 8001:8001 \
  -v ${PWD}/core/debug_files:/app/core/debug_files:Z \
  --security-opt label=disable \
  unfold-step2svg:latest

# 起動確認
podman ps -a --filter name=unfold-step2svg
```

**起動オプションの説明:**
- `-d`: バックグラウンドで実行
- `--name unfold-step2svg`: コンテナ名を指定
- `--restart always`: コンテナが停止した場合に自動再起動
- `-p 8001:8001`: ホストの8001ポートをコンテナの8001ポートにマッピング
- `-v ${PWD}/core/debug_files:/app/core/debug_files:Z`: デバッグファイル用ボリューム（SELinuxラベル付き）
- `--security-opt label=disable`: SELinuxラベルを無効化（必要に応じて）

### Step 5: 動作確認とテスト

#### 5.1 ヘルスチェック

```bash
# APIヘルスエンドポイントの確認
curl http://localhost:8001/api/health | python3 -m json.tool

# 期待される応答:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "opencascade_available": true,
#   "citygml_support": true,
#   "supported_formats": ["step", "stp", "citygml", "gml"]
# }
```

#### 5.2 コンテナログの確認

```bash
# リアルタイムログ表示
bash podman-deploy.sh logs

# または直接podmanコマンド
podman logs -f unfold-step2svg

# 過去100行のログを表示
podman logs --tail 100 unfold-step2svg
```

#### 5.3 APIテスト

```bash
# テスト用STEPファイルがある場合
curl -X POST \
  -F "file=@/path/to/sample.step" \
  -F "page_size=A4" \
  -F "layout_mode=multi_page" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg

# SVGファイルの確認
ls -lh papercraft.svg
```

---

## systemdサービス化

systemdサービスとして登録することで、OS起動時の自動起動やサービス管理が容易になります。

### 方法1: podman-deploy.shスクリプトを使用（推奨）

```bash
# systemdサービスファイルを生成
bash podman-deploy.sh systemd

# 生成されたサービスファイルを確認
cat container-unfold-step2svg.service

# ユーザーサービスとしてインストール
mkdir -p ~/.config/systemd/user/
mv container-unfold-step2svg.service ~/.config/systemd/user/

# systemdをリロード
systemctl --user daemon-reload

# サービスを有効化（ログイン時に自動起動）
systemctl --user enable container-unfold-step2svg.service

# サービスを開始
systemctl --user start container-unfold-step2svg.service

# サービスステータス確認
systemctl --user status container-unfold-step2svg.service

# ログ確認
journalctl --user -u container-unfold-step2svg.service -f
```

### 方法2: システムサービスとして登録（root権限が必要）

```bash
# systemdサービスファイルを手動作成
sudo tee /etc/systemd/system/unfold-step2svg.service > /dev/null <<'EOF'
[Unit]
Description=Unfold STEP2SVG API Service
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
Restart=always
RestartSec=10
ExecStartPre=/usr/bin/podman stop -i -t 10 unfold-step2svg
ExecStartPre=/usr/bin/podman rm -i -f unfold-step2svg
ExecStart=/usr/bin/podman run \
  --name unfold-step2svg \
  --replace \
  -p 8001:8001 \
  -v /opt/applications/Paper-CAD/backend/core/debug_files:/app/core/debug_files:Z \
  --security-opt label=disable \
  unfold-step2svg:latest
ExecStop=/usr/bin/podman stop -t 10 unfold-step2svg
ExecStopPost=/usr/bin/podman rm -f unfold-step2svg

[Install]
WantedBy=multi-user.target
EOF

# パスを環境に合わせて修正してください

# systemdをリロード
sudo systemctl daemon-reload

# サービスを有効化（OS起動時に自動起動）
sudo systemctl enable unfold-step2svg.service

# サービスを開始
sudo systemctl start unfold-step2svg.service

# サービスステータス確認
sudo systemctl status unfold-step2svg.service

# ログ確認
sudo journalctl -u unfold-step2svg.service -f
```

### systemdサービスの管理コマンド

```bash
# ユーザーサービスの場合
systemctl --user start container-unfold-step2svg.service    # 開始
systemctl --user stop container-unfold-step2svg.service     # 停止
systemctl --user restart container-unfold-step2svg.service  # 再起動
systemctl --user status container-unfold-step2svg.service   # ステータス確認

# システムサービスの場合（sudoが必要）
sudo systemctl start unfold-step2svg.service    # 開始
sudo systemctl stop unfold-step2svg.service     # 停止
sudo systemctl restart unfold-step2svg.service  # 再起動
sudo systemctl status unfold-step2svg.service   # ステータス確認
```

---

## セキュリティ設定

### SELinux設定

RHEL系OSではSELinuxがデフォルトで有効です。適切な設定を行います。

#### SELinux状態の確認

```bash
# SELinuxが有効か確認
getenforce
# 出力: Enforcing（強制）、Permissive（許可）、Disabled（無効）

# SELinuxのステータス詳細
sestatus
```

#### ポートコンテキストの追加

```bash
# ポート8001にHTTPポートコンテキストを追加
sudo semanage port -a -t http_port_t -p tcp 8001

# 設定確認
sudo semanage port -l | grep 8001
```

#### ボリュームマウント時のSELinuxラベル

```bash
# ボリュームマウント時に `:Z` オプションを使用（自動ラベル付け）
# podman-deploy.sh では既に設定済み
-v ${PWD}/core/debug_files:/app/core/debug_files:Z
```

#### トラブルシューティング（SELinux関連）

```bash
# SELinux拒否ログの確認
sudo ausearch -m avc -ts recent

# 一時的に許可モードに変更（テスト用のみ）
sudo setenforce 0  # Permissiveモード
# テスト後は必ず元に戻す
sudo setenforce 1  # Enforcingモード
```

### ファイアウォール設定（firewalld）

#### 基本設定

```bash
# firewalldが起動しているか確認
sudo systemctl status firewalld

# ポート8001を開放（パーマネント）
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --reload

# 設定確認
sudo firewall-cmd --list-ports

# 特定のIPアドレスからのみアクセスを許可（オプション）
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port protocol="tcp" port="8001" accept'
sudo firewall-cmd --reload
```

#### HTTPSリバースプロキシ経由でのアクセス（推奨）

Nginxなどのリバースプロキシを使用する場合：

```bash
# HTTPとHTTPSポートを開放
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# 8001ポートは外部に公開しない（localhostのみアクセス可能）
```

### rootlessモードでの実行（推奨）

Podmanはrootless（非root）モードで実行することでセキュリティが向上します。

```bash
# 現在のユーザーで実行（rootlessモード）
podman run -d \
  --name unfold-step2svg \
  --user 1000:1000 \
  -p 8001:8001 \
  --read-only \
  --tmpfs /tmp \
  --tmpfs /app/core/debug_files \
  unfold-step2svg:latest

# rootlessモードで実行されているか確認
podman ps --format "{{.Names}} {{.User}}"
```

**rootlessモードの利点:**
- root権限不要でコンテナ実行
- 万が一のコンテナ侵害時の影響範囲を限定
- マルチテナント環境での分離性向上

---

## プロダクション環境向け設定

### リソース制限

```bash
# CPU/メモリ制限付きでコンテナを起動
podman run -d \
  --name unfold-step2svg \
  --restart always \
  --memory="4g" \
  --memory-swap="6g" \
  --cpus="2.0" \
  --pids-limit=200 \
  -p 8001:8001 \
  -v ${PWD}/core/debug_files:/app/core/debug_files:Z \
  unfold-step2svg:latest

# リソース使用状況の監視
podman stats unfold-step2svg

# 実行中のコンテナのリソース制限を変更
podman update --memory="8g" --cpus="4" unfold-step2svg
```

### ログローテーション設定

```bash
# ログサイズ制限付きで起動
podman run -d \
  --name unfold-step2svg \
  --restart always \
  -p 8001:8001 \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  -v ${PWD}/core/debug_files:/app/core/debug_files:Z \
  unfold-step2svg:latest

# ログサイズ確認
podman inspect unfold-step2svg | grep -A 5 LogConfig
```

### リバースプロキシの設定（Nginx）

外部公開する場合はNginxなどのリバースプロキシを使用します。

```bash
# Nginxのインストール
sudo dnf install -y nginx

# 設定ファイルの作成
sudo tee /etc/nginx/conf.d/unfold-step2svg.conf > /dev/null <<'EOF'
upstream unfold_backend {
    server localhost:8001;
}

server {
    listen 80;
    server_name your-domain.com;  # 実際のドメイン名に変更

    # HTTPSへリダイレクト（Let's Encrypt設定後に有効化）
    # return 301 https://$host$request_uri;

    location /api/ {
        proxy_pass http://unfold_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # タイムアウト設定（大きなファイル処理用）
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;

        # アップロードサイズ制限
        client_max_body_size 100M;
    }
}
EOF

# Nginxの設定テスト
sudo nginx -t

# Nginxを起動・有効化
sudo systemctl enable nginx
sudo systemctl start nginx
```

### バックアップとリストア

#### イメージのエクスポート

```bash
# イメージをtarアーカイブとして保存
podman save unfold-step2svg:latest -o unfold-step2svg-backup.tar

# 別サーバーへ転送
scp unfold-step2svg-backup.tar user@remote-server:/tmp/

# リストア
podman load -i unfold-step2svg-backup.tar
```

#### ボリュームデータのバックアップ

```bash
# debug_filesディレクトリのバックアップ
tar -czf debug_files_backup_$(date +%Y%m%d).tar.gz core/debug_files/

# リストア
tar -xzf debug_files_backup_20250126.tar.gz
```

### モニタリング

#### Podmanイベントの監視

```bash
# コンテナイベントをリアルタイム監視
podman events --filter container=unfold-step2svg

# 特定期間のイベントを確認
podman events --since '2025-01-26 10:00:00' --filter container=unfold-step2svg
```

#### ヘルスチェックの自動化

cronジョブでヘルスチェックを定期実行し、異常時に通知します。

```bash
# ヘルスチェックスクリプトの作成
cat > ~/healthcheck_unfold.sh <<'EOF'
#!/bin/bash
HEALTH_URL="http://localhost:8001/api/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")

if [ "$RESPONSE" != "200" ]; then
    echo "Health check failed! HTTP status: $RESPONSE" | logger -t unfold-health
    # 通知処理（メール送信など）
    # echo "Unfold API health check failed" | mail -s "Alert: Unfold API Down" admin@example.com
fi
EOF

chmod +x ~/healthcheck_unfold.sh

# cronジョブに追加（5分ごとに実行）
crontab -e
# 以下を追加:
# */5 * * * * /home/youruser/healthcheck_unfold.sh
```

---

## トラブルシューティング

### コンテナが起動しない

#### 1. ログの確認

```bash
# コンテナログの詳細確認
podman logs unfold-step2svg 2>&1 | less

# podman-deploy.shでログ確認
bash podman-deploy.sh logs
```

#### 2. インタラクティブモードでデバッグ

```bash
# コンテナ内でシェルを起動
podman run -it --rm \
  -p 8001:8001 \
  -v ${PWD}/core/debug_files:/app/core/debug_files:Z \
  unfold-step2svg:latest /bin/bash

# コンテナ内で手動起動
conda activate unfold-step2svg
python main.py
```

#### 3. ポート競合の確認

```bash
# ポート8001が既に使用されているか確認
sudo ss -tlnp | grep 8001

# 使用中のプロセスを終了
sudo kill -9 $(sudo lsof -t -i:8001)
```

### メモリ不足エラー

#### OOM (Out of Memory) エラーの場合

```bash
# メモリ制限を増やしてコンテナを起動
podman run -d \
  --name unfold-step2svg \
  --memory="8g" \
  --memory-swap="12g" \
  -p 8001:8001 \
  unfold-step2svg:latest

# システムメモリの確認
free -h

# コンテナのメモリ使用状況を監視
podman stats unfold-step2svg
```

### ネットワーク接続の問題

#### ポートバインディングの確認

```bash
# コンテナのポートマッピング確認
podman port unfold-step2svg

# ネットワーク設定の詳細確認
podman inspect unfold-step2svg | grep -A 20 NetworkSettings
```

#### ホストネットワークモードで実行（最終手段）

```bash
# ホストネットワークを直接使用
podman run -d \
  --name unfold-step2svg \
  --network host \
  unfold-step2svg:latest

# この場合、ポートマッピング不要（ホストの8001ポートを直接使用）
```

### SELinux関連の問題

#### ボリュームマウントエラー

```bash
# SELinuxコンテキストの確認
ls -Z core/debug_files

# SELinuxラベルを手動で設定
sudo chcon -Rt svirt_sandbox_file_t core/debug_files

# または、ボリュームマウント時に :Z オプションを使用
-v ${PWD}/core/debug_files:/app/core/debug_files:Z
```

#### ポートアクセス拒否

```bash
# SELinux拒否ログの確認
sudo ausearch -m avc -ts recent | grep 8001

# ポートラベルの追加
sudo semanage port -a -t http_port_t -p tcp 8001
```

### ビルドエラー

#### Conda環境作成の失敗

```bash
# キャッシュをクリアして再ビルド
podman build --no-cache -f Containerfile -t unfold-step2svg:latest .

# environment-docker.ymlの確認
cat environment-docker.yml
```

#### ネットワークタイムアウト

```bash
# DNSサーバーの設定
# /etc/containers/containers.conf に追加
sudo tee -a /etc/containers/containers.conf > /dev/null <<'EOF'
[network]
dns_servers = ["8.8.8.8", "8.8.4.4"]
EOF

# 再ビルド
podman build -f Containerfile -t unfold-step2svg:latest .
```

### パフォーマンスの問題

#### レスポンスが遅い

```bash
# CPU/メモリリソースを増やす
podman update --cpus="4" --memory="8g" unfold-step2svg

# コンテナのリソース使用状況を確認
podman stats unfold-step2svg
```

#### ディスクI/O遅延

```bash
# ボリュームのマウントオプションを最適化
-v ${PWD}/core/debug_files:/app/core/debug_files:Z,rw,noatime

# overlayストレージドライバの確認
podman info | grep -A 5 graphDriverName
```

### その他のデバッグコマンド

```bash
# コンテナの詳細情報を確認
podman inspect unfold-step2svg | less

# コンテナ内でコマンド実行
podman exec -it unfold-step2svg /bin/bash

# Conda環境の確認
podman exec -it unfold-step2svg conda env list

# Pythonパッケージの確認
podman exec -it unfold-step2svg conda run -n unfold-step2svg pip list
```

---

## podman-deploy.sh 全コマンドリファレンス

### 基本コマンド

```bash
# ビルドと起動を一度に実行
bash podman-deploy.sh build-run

# イメージのビルドのみ
bash podman-deploy.sh build

# コンテナの起動のみ
bash podman-deploy.sh run

# コンテナの停止
bash podman-deploy.sh stop

# コンテナとイメージを削除
bash podman-deploy.sh remove
```

### 管理コマンド

```bash
# コンテナログを表示（リアルタイム）
bash podman-deploy.sh logs

# コンテナ内シェルに入る
bash podman-deploy.sh shell

# systemdサービスファイルを生成
bash podman-deploy.sh systemd

# コンテナとイメージのステータス確認
bash podman-deploy.sh status
```

### 環境変数でのカスタマイズ

```bash
# ポート番号を変更
PORT=9000 bash podman-deploy.sh run

# 別のContainerfileを使用
CONTAINERFILE=Dockerfile bash podman-deploy.sh build
```

---

## アップデートとメンテナンス

### アプリケーションの更新

```bash
# 最新コードを取得
cd /opt/applications/Paper-CAD/backend
git pull origin main

# コンテナを停止
bash podman-deploy.sh stop

# イメージを再ビルド
bash podman-deploy.sh build

# コンテナを起動
bash podman-deploy.sh run

# または一括で実行
git pull origin main && bash podman-deploy.sh build-run
```

### Podmanのアップデート

```bash
# Podmanを最新バージョンに更新
sudo dnf update -y podman

# バージョン確認
podman --version
```

### 古いイメージとコンテナのクリーンアップ

```bash
# 停止中のコンテナを削除
podman container prune -f

# 未使用のイメージを削除
podman image prune -a -f

# 全てのPodmanリソースをクリーンアップ（注意）
podman system prune -a -f --volumes
```

---

## サポート

### ログの収集

問題報告時には以下の情報を提供してください：

```bash
# システム情報
cat /etc/os-release
podman --version
podman info

# コンテナログ
podman logs unfold-step2svg > container.log 2>&1

# SELinuxログ
sudo ausearch -m avc -ts recent > selinux.log

# systemdログ（サービス化している場合）
journalctl --user -u container-unfold-step2svg.service > systemd.log
```

### 問題報告先

- **GitHub Issues**: https://github.com/Soynyuu/Paper-CAD/issues
- **メール**: 管理者に連絡
- **デバッグファイル**: `core/debug_files/` ディレクトリを確認

---

## 参考資料

- [Podman公式ドキュメント](https://docs.podman.io/)
- [RHEL 9 コンテナガイド](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/index)
- [SELinux ユーザーガイド](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/index)
- [Paper-CAD プロジェクト](https://github.com/Soynyuu/Paper-CAD)

---

## ライセンス

Paper-CAD プロジェクトのライセンスに従います。

---

**最終更新**: 2025年1月
