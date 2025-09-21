<div align="center">

# Paper-CAD

**紙の建物模型制作を、苦しい試練から創造的な楽しみへ**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue?logo=typescript)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)

[**🎯 デモを試す**](#quick-start) • [**📚 ドキュメント**](#documentation) • [**🤝 コントリビュート**](#contributing)

</div>

---

## 🎯 なぜPaper-CADが必要なのか

### 模型制作における「見えない壁」

紙の建物模型（ジオラマストラクチャー）制作は、**設計→印刷→切り出し→接着→塗装**という一見シンプルな工程に見えます。

しかし実際には、**制作時間の約70%が「展開図を描く」設計作業**に費やされます。

写真から立体を平面に展開する作業は、高度な空間認識力と数学的知識を必要とする**職人芸の領域**。AutoCADやJw_cadを使いこなしても、初心者は何度も失敗を繰り返し、経験者でさえ大きなストレスを抱える、模型制作で最も**"つらい部分"**でした。

### 開発者の原体験

> 私自身、鉄道研究部で4年間模型制作に取り組み、最初の2年間は大量の失敗作を生み出しながらノウハウを身につけました。後輩に技術を伝えようとしても、言葉では説明できない暗黙知の壁にぶつかり、もどかしさを覚える日々。
>
> 「もっと直感的に設計できたらいいのに！」
>
> この想いが、Paper-CADを生み出す原動力となりました。

## ✨ Paper-CADが実現すること

Paper-CADは、紙の建物模型制作を**直感的に効率化・自動化**するWeb CADアプリケーションです。

<div align="center">
  <table>
    <tr>
      <th width="50%">🔄 従来の制作フロー</th>
      <th width="50%">✨ Paper-CADによる新しいフロー</th>
    </tr>
    <tr>
      <td>
        1. 写真や資料から建物を観察<br>
        2. 頭の中で立体を展開図に変換<br>
        3. 2D CADで一面ずつ描画<br>
        4. 試作・失敗・修正を繰り返す<br>
        <b>⏱️ 設計だけで数日〜数週間</b>
      </td>
      <td>
        1. 3Dモデルを直感的に作成/インポート<br>
        2. ワンクリックで展開図を自動生成<br>
        3. 必要に応じて微調整<br>
        4. SVG形式で出力・印刷<br>
        <b>⏱️ 数分〜数時間で完成</b>
      </td>
    </tr>
  </table>
</div>

### 🚀 主要機能

- **3D→2D自動展開**: 3Dモデルから印刷用展開図（SVG）を自動生成
- **CityGML対応**: 国土交通省提供の3D都市モデルを直接活用
- **直感的な3D編集**: Web上で動作する本格的なCAD機能
- **面番号の同期**: 3D表示と2D展開図で対応する面を自動ナンバリング

## 🌟 誰のためのツールか

### 🎓 初心者の方へ
- 模型制作の最大の壁だった「設計」のハードルを大幅に下げます
- 空間認識力や数学的知識がなくても、直感的に建物模型を作成できます
- 失敗を恐れず、気軽に模型制作を楽しめます

### 🏗️ 経験者の方へ
- 1つの建物にかかる時間を**大幅に削減**（数日→数時間）
- 従来は不可能だった規模の**街並み全体の制作**が可能に
- 設計の苦労から解放され、創造的な部分に集中できます

### 💡 新しい使い方の提案
- 🏠 新築前に設計図の3Dモデルから「完成後の自宅模型」を作成
- 🎬 好きなアニメや映画の街並みを再現
- 📸 思い出の建物を模型でアーカイブ
- 🎓 建築学生の学習ツールとして活用

## 🛠️ システム構成

Paper-CADは2つの統合プロジェクトから構成されています：

<div align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <h3>🎨 chili3d</h3>
        <b>ブラウザベース3D CAD</b><br>
        <i>3Dモデルの作成・編集・エクスポート</i>
      </td>
      <td align="center" width="50%">
        <h3>📐 unfold-step2svg</h3>
        <b>展開図生成エンジン</b><br>
        <i>3Dモデルから2D展開図への自動変換</i>
      </td>
    </tr>
  </table>
</div>

### 🎨 **chili3d** の特徴

<details open>
<summary><b>プロフェッショナルグレードのCAD機能</b></summary>

- 🔧 **高度なモデリングツール**: ブラウザ上で動作する本格的な3D CAD
- ⚡ **WebAssembly高速化**: OpenCascadeをWASMで実装し、ネイティブに迫るパフォーマンス
- 🎯 **スマートスナップシステム**: 精密な3Dモデリングを支援
- 🌐 **CityGML対応**: 国土交通省の3D都市モデルを直接インポート可能
- 📦 **モジュラー設計**: 11パッケージのモノレポ構造で拡張性を確保

> **Note**: [xiangechen/chili3d](https://github.com/xiangechen/chili3d)をフォークし、ペーパークラフト機能を拡張

</details>

### 📐 **unfold-step2svg** の特徴

<details open>
<summary><b>インテリジェント展開図生成</b></summary>

- 🔄 **自動展開アルゴリズム**: 3Dモデルから最適な展開図を自動生成
- 📄 **複数フォーマット対応**: A4, A3, Letter等の用紙サイズに自動最適化
- 🔢 **面番号システム**: 3D表示と展開図の面を自動対応付け
- 🏗️ **建築モデル対応**: CityGML/IFC形式の都市・建築モデルに対応
- 🚀 **高速処理**: FastAPIによる効率的な変換処理

</details>

## 🛠️ 技術スタック

<div align="center">

| Project | Frontend | Backend | Core Tech | Build Tools |
|---------|----------|---------|-----------|-------------|
| **chili3d** | TypeScript<br>Three.js<br>Custom UI | WebAssembly<br>OpenCascade | OCCT 7.9<br>React-like UI | Rspack<br>CMake |
| **unfold-step2svg** | - | Python<br>FastAPI | OpenCASCADE<br>pythonocc-core | Conda<br>pip |

</div>

## 🚀 Quick Start

### chili3d

```bash
# リポジトリのクローン
git clone https://github.com/Soynyuu/chili3d
cd chili3d

# 依存関係のインストール
npm install

# 開発サーバーの起動
npm run dev

# ブラウザで開く
# http://localhost:8080
```

### unfold-step2svg

```bash
# リポジトリのクローン
git clone https://github.com/Soynyuu/unfold-step2svg
cd unfold-step2svg

# Conda環境の作成と有効化
conda env create -f environment.yml
conda activate unfold-step2svg

# サーバーの起動
python main.py

# APIエンドポイント
# http://localhost:8001
```

## 📖 Documentation

### 開発コマンド

<details>
<summary><b>chili3d コマンド一覧</b></summary>

```bash
npm run dev              # 開発サーバー起動 (http://localhost:8080)
npm run build           # プロダクションビルド
npm run build:wasm      # WebAssemblyモジュールのビルド
npm test                # Jestテストの実行
npm run format          # コードフォーマット (TS & C++)
npm run setup:wasm      # WASM依存関係のセットアップ
```

</details>

<details>
<summary><b>unfold-step2svg コマンド一覧</b></summary>

```bash
python main.py                          # FastAPIサーバー起動
curl http://localhost:8001/api/health  # ヘルスチェック

# APIエンドポイント例
POST /api/unfold/step     # STEPファイルの展開
POST /api/unfold/citygml  # CityGMLファイルの展開
GET  /api/health          # システムステータス
```

</details>

## 🏗️ アーキテクチャ

### chili3d - モノレポ構造

```
chili3d/
├── packages/
│   ├── chili-core/        # コアインターフェース
│   ├── chili-wasm/        # WebAssemblyバインディング
│   ├── chili-three/       # Three.js実装
│   ├── chili-ui/          # UIフレームワーク
│   ├── chili/             # メインアプリケーション
│   └── chili-web/         # Webエントリポイント
└── cpp/                   # C++ OpenCascadeコード
```

### unfold-step2svg - パイプライン構造

```
unfold-step2svg/
├── core/
│   ├── geometry/          # 幾何学処理
│   ├── unfold/           # 展開アルゴリズム
│   ├── layout/           # レイアウト最適化
│   └── debug_files/      # デバッグ出力
├── api/                  # FastAPI エンドポイント
└── converters/           # ファイル形式変換
```

## 🤝 Contributing

プロジェクトへの貢献を歓迎します！

### 開発の流れ

1. 🍴 リポジトリをフォーク
2. 🌿 フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 📝 変更をコミット (`git commit -m 'Add amazing feature'`)
4. 📤 ブランチをプッシュ (`git push origin feature/amazing-feature`)
5. 🔄 プルリクエストを作成

### コーディング規約

- **TypeScript**: ESLint + Prettier設定に従う
- **Python**: PEP 8準拠、型ヒント使用推奨
- **C++**: clang-format使用
- **コミット**: Conventional Commits形式

## 📄 ライセンス

- **chili3d**: [AGPL-3.0](./chili3d/LICENSE) (商用ライセンス利用可)
- **unfold-step2svg**: [MIT](./unfold-step2svg/LICENSE)

## 🙏 謝辞

- [未踏ジュニア](https://jr.mitou.org/) - プロジェクトサポート
- [xiangechen/chili3d](https://github.com/xiangechen/chili3d) - オリジナルのchili3dプロジェクト（AGPL-3.0ライセンス）
- [OpenCASCADE Technology](https://www.opencascade.com/) - 3D CADカーネル
- [Three.js](https://threejs.org/) - 3Dグラフィックスライブラリ

## 📬 お問い合わせ

- **chili3d**: [GitHub Issues](https://github.com/Soynyuu/chili3d/issues)
- **unfold-step2svg**: [GitHub Issues](https://github.com/Soynyuu/unfold-step2svg/issues)

---

## 🚀 ビジョン

> 模型設計を「苦しい試練」から「ワクワクする創造」へ

Paper-CADは、単なるツールではありません。

紙の建物模型制作という伝統的な趣味を、より多くの人に開かれた、創造的な活動へと変革するプラットフォームです。

熟練者にとっては新たな挑戦の場を、初心者にとっては気軽な入口を提供し、紙模型文化の新しい可能性を切り拓いていきます。

---

<div align="center">

**Made with ❤️ for 未踏ジュニア 2025**

*模型制作の楽しさを、すべての人に。*

[⬆ トップへ戻る](#paper-cad)

</div>