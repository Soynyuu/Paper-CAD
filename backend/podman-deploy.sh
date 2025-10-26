#!/bin/bash

# Podmanデプロイスクリプト for Rocky Linux
# Rootlessモードでの実行を前提

set -e

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 設定
IMAGE_NAME="unfold-step2svg"
CONTAINER_NAME="unfold-step2svg"
PORT="${PORT:-8001}"
DEBUG_VOLUME="${PWD}/core/debug_files:/app/core/debug_files"
CONTAINERFILE="${CONTAINERFILE:-Containerfile}"

echo -e "${GREEN}=== Unfold-STEP2SVG Podman Deployment ===${NC}"

# Podmanインストール確認
if ! command -v podman &> /dev/null; then
    echo -e "${RED}Error: Podman is not installed${NC}"
    echo "Install with: sudo dnf install podman podman-compose"
    exit 1
fi

# アクション選択
ACTION=${1:-build-run}

case $ACTION in
    build)
        echo -e "${YELLOW}Building container image...${NC}"

        # Containerfileが存在するか確認
        if [ ! -f "${CONTAINERFILE}" ]; then
            echo -e "${RED}Error: ${CONTAINERFILE} not found${NC}"
            exit 1
        fi

        # environment-docker.ymlが存在するか確認
        if [ ! -f "environment-docker.yml" ]; then
            echo -e "${RED}Error: environment-docker.yml not found${NC}"
            exit 1
        fi

        podman build --no-cache -f ${CONTAINERFILE} -t ${IMAGE_NAME}:latest .
        echo -e "${GREEN}Build completed!${NC}"
        echo -e "${GREEN}Image: ${IMAGE_NAME}:latest${NC}"
        ;;
    
    run)
        echo -e "${YELLOW}Starting container...${NC}"
        
        # 既存コンテナの停止と削除
        podman stop ${CONTAINER_NAME} 2>/dev/null || true
        podman rm ${CONTAINER_NAME} 2>/dev/null || true
        
        # debug_filesディレクトリの作成
        mkdir -p core/debug_files
        
        # コンテナ実行（Rootlessモード）
        # 本番環境用の環境変数を明示的に設定
        podman run -d \
            --name ${CONTAINER_NAME} \
            --restart always \
            -p ${PORT}:8001 \
            -v ${DEBUG_VOLUME}:Z \
            -e FRONTEND_URL=https://app.paper-cad.soynyuu.com \
            -e CORS_ALLOW_ALL=false \
            -e PORT=8001 \
            --security-opt label=disable \
            ${IMAGE_NAME}:latest
        
        echo -e "${GREEN}Container started on port ${PORT}${NC}"
        echo "Check health: curl http://localhost:${PORT}/api/health"
        ;;
    
    build-run)
        echo -e "${YELLOW}Building and running container...${NC}"
        bash "$0" build
        bash "$0" run
        ;;

    stop)
        echo -e "${YELLOW}Stopping container...${NC}"
        podman stop ${CONTAINER_NAME}
        echo -e "${GREEN}Container stopped${NC}"
        ;;
    
    remove)
        echo -e "${YELLOW}Removing container and image...${NC}"
        podman stop ${CONTAINER_NAME} 2>/dev/null || true
        podman rm ${CONTAINER_NAME} 2>/dev/null || true
        podman rmi ${IMAGE_NAME}:latest 2>/dev/null || true
        echo -e "${GREEN}Cleanup completed${NC}"
        ;;
    
    logs)
        podman logs -f ${CONTAINER_NAME}
        ;;
    
    shell)
        echo -e "${YELLOW}Entering container shell...${NC}"
        podman exec -it ${CONTAINER_NAME} /bin/bash
        ;;
    
    systemd)
        echo -e "${YELLOW}Generating systemd service...${NC}"
        
        # systemdサービスファイルの生成
        podman generate systemd \
            --name ${CONTAINER_NAME} \
            --files \
            --new \
            --restart-policy always
        
        echo -e "${GREEN}Systemd service file generated!${NC}"
        echo "To install:"
        echo "  1. sudo cp container-${CONTAINER_NAME}.service /etc/systemd/system/"
        echo "  2. sudo systemctl daemon-reload"
        echo "  3. sudo systemctl enable container-${CONTAINER_NAME}.service"
        echo "  4. sudo systemctl start container-${CONTAINER_NAME}.service"
        ;;
    
    status)
        echo -e "${YELLOW}Container status:${NC}"
        podman ps -a --filter name=${CONTAINER_NAME}
        echo ""
        echo -e "${YELLOW}Image status:${NC}"
        podman images ${IMAGE_NAME}
        echo ""
        echo -e "${YELLOW}Health check:${NC}"
        curl -s http://localhost:${PORT}/api/health | python3 -m json.tool || echo "Service not responding"
        ;;
    
    *)
        echo "Usage: $0 {build|run|build-run|stop|remove|logs|shell|systemd|status}"
        echo ""
        echo "Commands:"
        echo "  build      - Build container image"
        echo "  run        - Run container"
        echo "  build-run  - Build and run (default)"
        echo "  stop       - Stop container"
        echo "  remove     - Remove container and image"
        echo "  logs       - Show container logs"
        echo "  shell      - Enter container shell"
        echo "  systemd    - Generate systemd service"
        echo "  status     - Show container status"
        exit 1
        ;;
esac