#!/bin/bash
# Hugging Face Spaces デプロイスクリプト
#
# 前提条件:
#   1. huggingface-cli がインストール済み: pip install huggingface_hub
#   2. HF にログイン済み: huggingface-cli login
#   3. HF Space が作成済み (SDK: Docker)
#
# 使い方:
#   HF_SPACE=username/space-name ./deploy-hf.sh
#
# 環境変数は HF Space の Settings > Variables / Secrets で設定:
#   - FRONTEND_URL (フロントエンドの URL)
#   - ENV=production
#   - WORKERS=1

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# --- 設定 ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HF_SPACE="${HF_SPACE:-}"
TEMP_DIR=""

# --- ヘルパー ---
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
        info "一時ディレクトリを削除しました"
    fi
}
trap cleanup EXIT

# --- 事前チェック ---
if [ -z "$HF_SPACE" ]; then
    error "HF_SPACE が未設定です"
    echo "使い方: HF_SPACE=username/space-name $0"
    exit 1
fi

if ! command -v huggingface-cli &>/dev/null; then
    error "huggingface-cli がインストールされていません"
    echo "インストール: pip install huggingface_hub"
    exit 1
fi

if ! huggingface-cli whoami &>/dev/null; then
    error "HF にログインしていません"
    echo "ログイン: huggingface-cli login"
    exit 1
fi

info "=== Paper-CAD HF Spaces デプロイ ==="
info "Space: ${HF_SPACE}"

# --- 一時ディレクトリにデプロイ用ファイルを準備 ---
TEMP_DIR="$(mktemp -d)"
info "一時ディレクトリ: ${TEMP_DIR}"

# HF Space リポをクローン
info "HF Space リポをクローン中..."
git clone "https://huggingface.co/spaces/${HF_SPACE}" "$TEMP_DIR/space"

# backend のファイルをコピー（.dockerignore のルールに従う）
info "バックエンドファイルをコピー中..."
rsync -av --exclude-from="$SCRIPT_DIR/.dockerignore" \
    --exclude='Dockerfile' \
    --exclude='Dockerfile.mamba' \
    --exclude='Containerfile' \
    --exclude='docker-compose.yml' \
    --exclude='podman-deploy.sh' \
    --exclude='deploy-hf.sh' \
    --exclude='environment.yml' \
    "$SCRIPT_DIR/" "$TEMP_DIR/space/"

# Dockerfile.hf → Dockerfile にリネームしてコピー
cp "$SCRIPT_DIR/Dockerfile.hf" "$TEMP_DIR/space/Dockerfile"

# environment-docker.yml をコピー（Dockerfile が参照する）
cp "$SCRIPT_DIR/environment-docker.yml" "$TEMP_DIR/space/environment-docker.yml"

# HF Space 用の README.md を生成（YAML frontmatter が必要）
cat > "$TEMP_DIR/space/README.md" << 'README_EOF'
---
title: Paper-CAD API
emoji: 📐
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Paper-CAD Backend API

3D CAD models to 2D papercraft patterns (SVG/PDF).

- **API Docs**: `/docs`
- **Health Check**: `/api/health`
README_EOF

# --- HF Space にプッシュ ---
info "HF Space にプッシュ中..."
cd "$TEMP_DIR/space"
git add -A
git diff --cached --quiet && { info "変更なし。デプロイをスキップします。"; exit 0; }
git commit -m "deploy: update Paper-CAD backend"
git push

info "=== デプロイ完了 ==="
info "Space URL: https://huggingface.co/spaces/${HF_SPACE}"
info "API URL:   https://$(echo "$HF_SPACE" | tr '/' '-').hf.space"
echo ""
warn "ビルドには 10-15 分かかります。HF Space のログで進捗を確認してください。"
warn "初回デプロイ後、Settings で環境変数を設定してください:"
echo "  - FRONTEND_URL = <フロントエンドの URL>"
