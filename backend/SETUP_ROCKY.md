# How to setup Podman container

## セットアップ手順

### 1. システムの準備

```bash
# OS確認
cat /etc/rocky-release

# 必要なツールのインストール
sudo dnf update -y
sudo dnf install -y podman git curl

# Podmanバージョン確認
podman --version
```

### 2. プロジェクトの取得

```bash
# リポジトリをクローン
git clone https://github.com/soynyuu/paper-cad
cd paper-cad
```

### 3. コンテナイメージのビルド

```bash
# Containerfileを使用してビルド（プラットフォーム非依存）
podman build -f Containerfile -t paper-cad .

# ビルドの確認
podman images | grep paper-cad
```

### 4. コンテナの実行

```bash
# コンテナをバックグラウンドで起動
podman run -d \
  --name unfold-app \
  -p 8001:8001 \
  --restart unless-stopped \
  paper-cad

# 起動確認
podman ps

# ログの確認
podman run -d \
  --name unfold-app \
  -p 8001:8001 \
  --restart unless-stopped \
  paper-cad
```

### 5. 動作確認

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
```

### 6. APIテスト

```bash
# テスト用STEPファイルがある場合
curl -X POST \
  -F "file=@sample.step" \
  http://localhost:8001/api/step/unfold \
  -o papercraft.svg

# SVGファイルの確認
ls -la papercraft.svg
```

## systemd サービス設定（オプション）

### 自動起動設定

```bash
# systemdユニットファイルの生成
podman generate systemd --name unfold-app \
  --files \
  --new \
  --restart-policy=always

# ユーザーサービスディレクトリに移動
mkdir -p ~/.config/systemd/user/
mv container-unfold-app.service ~/.config/systemd/user/

# サービスの有効化と起動
systemctl --user daemon-reload
systemctl --user enable container-unfold-app.service
systemctl --user start container-unfold-app.service

# ステータス確認
systemctl --user status container-unfold-app.service
```

## ファイアウォール設定

```bash
# ポート8001を開放（firewalldを使用している場合）
sudo firewall-cmd --add-port=8001/tcp --permanent
sudo firewall-cmd --reload

# 設定確認
sudo firewall-cmd --list-ports
```

## SELinux設定（必要な場合）

```bash
# SELinuxが有効か確認
getenforce

# Enforcingの場合、ポートコンテキストを追加
sudo semanage port -a -t http_port_t -p tcp 8001

# または一時的に許可モードに変更（テスト用）
sudo setenforce 0
```

## トラブルシューティング

### コンテナが起動しない場合

```bash
# 詳細なエラーログを確認
podman logs unfold-app 2>&1

# インタラクティブモードで起動してデバッグ
podman run -it --rm -p 8001:8001 paper-cad /bin/bash
```

### メモリ不足エラー

```bash
# リソース制限付きで実行
podman run -d \
  --name unfold-app \
  --memory="4g" \
  --cpus="2" \
  -p 8001:8001 \
  paper-cad
```

### ネットワーク接続の問題

```bash
# ポートバインディングの確認
ss -tlnp | grep 8001

# コンテナのネットワーク確認
podman port unfold-app

# ホストネットワークモードで実行（最終手段）
podman run -d \
  --name unfold-app \
  --network host \
  paper-cad
```
## コンテナの管理

```bash
# コンテナの停止
podman stop unfold-app

# コンテナの削除
podman rm unfold-app

# イメージの削除
podman rmi paper-cad

# すべてクリーンアップ
podman system prune -a
```

## Podman-Composeの使用（オプション）

```bash
# podman-composeのインストール
sudo dnf install -y python3-pip
pip3 install --user podman-compose

# docker-compose.ymlがある場合
podman-compose up -d

# ログ確認
podman-compose logs -f
```

## パフォーマンス最適化

```bash
# CPUとメモリの使用状況確認
podman stats unfold-app

# リソース制限の調整
podman update --memory="8g" --cpus="4" unfold-app
```

## セキュリティ設定

```bash
# rootlessコンテナとして実行（推奨）
podman run -d \
  --name unfold-app \
  --user 1000:1000 \
  -p 8001:8001 \
  --read-only \
  --tmpfs /tmp \
  paper-cad
```

## ログローテーション設定

```bash
# ログサイズ制限付きで実行
podman run -d \
  --name unfold-app \
  -p 8001:8001 \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  paper-cad
```

## 問題が解決しない場合

1. GitHub Issuesで報告: https://github.com/soynyuu/paper-cad/issues
2. デバッグファイルの確認: `core/debug_files/`
3. Podmanのバージョンアップグレード検討

---
