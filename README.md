# Paper-CAD

**建物模型制作のための3D→2D展開図自動生成ツール**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.8-blue.svg)](https://www.typescriptlang.org/)
[![未踏ジュニア](https://img.shields.io/badge/未踏ジュニア-2025-orange.svg)](https://jr.mitou.org/)

## 概要

Paper-CADは建物模型制作のためのWebベースCADツールです。3D建物モデルを作成・インポートし、紙用2D展開図（SVG）へ自動変換することが可能です。

これまでは立体構造物である建物を平面に展開する"設計"作業が模型制作上の大きな負担でしたが、Paper-CADでは3D建物モデルから展開図を自動生成することで直感的・簡単に設計作業が行えます。これにより、模型制作のハードルを下げ、初心者も経験者も短時間で高精度な街並みを制作できるようになります。

## 主な特徴

### 🏢 建物モデリング
- **3Dモデル作成**: ブラウザ上で直感的に建物の3Dモデルを作成
- **STEPインポート**: 既存のCADデータ（STEP形式）をインポート可能
- **リアルタイムプレビュー**: 3Dビューで建物をあらゆる角度から確認

### 📐 展開図自動生成
- **高精度展開**: OpenCASCADE技術による正確な展開処理
- **折り線・切り線**: 組み立てに必要な線種を自動判別
- **組み立てタブ**: のりしろタブを自動配置
- **面番号管理**: 組み立て順序を示す面番号を付与

### 🖨️ 印刷最適化
- **複数用紙サイズ対応**: A4、A3、Letter用紙に対応
- **レイアウト自動調整**: 用紙サイズに合わせて展開図を最適配置
- **スケール調整**: 模型のサイズを自由に調整可能
- **SVGエクスポート**: 高品質な印刷用SVGファイルを出力

## セットアップ

### 前提条件
- Node.js 18以上
- Python 3.10以上
- Conda（推奨）またはPython仮想環境

### インストール手順

#### 1. リポジトリのクローン
```bash
git clone https://github.com/yourusername/Paper-CAD.git
cd Paper-CAD
```

#### 2. バックエンドのセットアップ
```bash
cd backend

# Conda環境の作成（推奨）
conda env create -f environment.yml
conda activate paper-cad

# または、pip環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# サーバー起動
python main.py  # http://localhost:8001
```

#### 3. フロントエンドのセットアップ
```bash
cd ../frontend

# 依存パッケージのインストール
npm install

# WebAssemblyのビルド（初回のみ）
npm run setup:wasm
npm run build:wasm

# 開発サーバー起動
npm run dev  # http://localhost:3000
```

## 使い方

### 基本的なワークフロー

1. **3Dモデルの準備**
   - Paper-CADで新規作成、または
   - 既存のSTEPファイルをインポート

2. **展開設定の調整**
   - 用紙サイズ（A4/A3/Letter）を選択
   - スケールファクターを設定
   - 向き（縦/横）を選択

3. **展開図の生成**
   - 「展開」ボタンをクリック
   - プレビューで確認

4. **ダウンロード・印刷**
   - SVGファイルをダウンロード
   - 印刷して切り抜き、組み立て

### APIの使用（上級者向け）

STEPファイルから直接SVGを生成：
```bash
curl -X POST \
  -F "file=@building.step" \
  -F "page_format=A4" \
  -F "scale_factor=0.01" \
  "http://localhost:8001/api/step/unfold" \
  -o building.svg
```

## 技術スタック

### フロントエンド
- **フレームワーク**: TypeScript + Custom Web Components
- **3D描画**: Three.js
- **CADカーネル**: WebAssembly (C++/Emscripten)
- **ビルドツール**: Rspack
- **UI**: Chili UI Framework

### バックエンド
- **フレームワーク**: FastAPI (Python)
- **CADエンジン**: OpenCASCADE Technology
- **展開アルゴリズム**: カスタム実装
- **コンテナ**: Docker/Podman対応

## プロジェクト構成

```
Paper-CAD/
├── frontend/           # Webフロントエンド
│   ├── packages/       # モジュール群
│   │   ├── chili/      # メインアプリケーション
│   │   ├── chili-ui/   # UIコンポーネント
│   │   ├── chili-core/ # コアロジック
│   │   └── chili-three/ # 3D描画
│   └── cpp/            # WebAssemblyソース
└── backend/            # APIサーバー
    ├── core/           # 展開処理エンジン
    ├── api/            # FastAPIエンドポイント
    └── services/       # ビジネスロジック
```

## 開発に参加する

### コントリビューション
Issue報告やPull Requestを歓迎します。詳細は[CONTRIBUTING.md](CONTRIBUTING.md)をご覧ください。

### 開発環境
```bash
# テスト実行（フロントエンド）
cd frontend && npm test

# テスト実行（バックエンド）
cd backend && pytest

# フォーマット
npm run format  # フロントエンド
black .         # バックエンド
```

## ロードマップ

- [ ] 複雑な建物形状への対応強化
- [ ] テクスチャマッピング機能
- [ ] 複数建物の一括処理
- [ ] 組み立て手順書の自動生成
- [ ] AR組み立てガイド
- [ ] コラボレーション機能

## ライセンス

MIT License - 詳細は[LICENSE](LICENSE)ファイルをご覧ください。

## 謝辞

- OpenCASCADE Technology
- 一般社団法人未踏 未踏ジュニア（2025年度採択プロジェクト）
- すべてのコントリビューターとユーザーの皆様

## サポート

- **ドキュメント**: [docs.paper-cad.io](https://docs.paper-cad.io)
- **Issue報告**: [GitHub Issues](https://github.com/yourusername/Paper-CAD/issues)
- **ディスカッション**: [GitHub Discussions](https://github.com/yourusername/Paper-CAD/discussions)

---

**Paper-CAD** - 建物模型制作を、もっと楽しく、もっと簡単に。