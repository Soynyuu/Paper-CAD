# Miniconda3ベースイメージを使用
FROM continuumio/miniconda3:24.11.1-0

# 作業ディレクトリの設定
WORKDIR /app

# システムパッケージの更新とタイムゾーン設定
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/share/zoneinfo/Asia/Tokyo /etc/localtime

# Conda環境ファイルをコピー
COPY environment.yml .

# Conda環境の作成
RUN conda env create -f environment.yml && \
    conda clean -afy

# アプリケーションコードをコピー
COPY . .

# ポート8001を公開
EXPOSE 8001

# Conda環境をアクティベートしてアプリケーションを起動
SHELL ["conda", "run", "-n", "paper-cad", "/bin/bash", "-c"]

# ヘルスチェックは docker-compose.yml / podman-deploy.sh で定義
# Dockerfileでの定義は削除（conda runの繰り返し実行によるロック問題を回避）

# アプリケーション起動
CMD ["conda", "run", "--no-capture-output", "-n", "paper-cad", "python", "main.py"]