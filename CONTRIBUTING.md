# コントリビューションガイド

Paper-CAD へのコントリビューションに興味をお持ちいただきありがとうございます！このドキュメントでは、プロジェクトへの貢献方法について説明します。

## 行動規範

このプロジェクトでは、[行動規範](CODE_OF_CONDUCT.md)を採用しています。プロジェクトに参加することで、この規範を遵守することに同意したものとみなされます。

## 貢献の方法

### バグ報告

バグを発見した場合は、GitHub Issues で報告してください：

1. 既存の Issue を検索して、同じ問題が報告されていないか確認
2. 新しい Issue を作成し、以下の情報を含める：
   - バグの明確な説明
   - 再現手順
   - 期待される動作
   - 実際の動作
   - スクリーンショット（該当する場合）
   - 環境情報（OS、ブラウザ、Node.js バージョンなど）

### 機能リクエスト

新機能のアイデアがある場合：

1. まず Issue を作成して提案を議論
2. 実装の方向性が合意されてから開発を開始

### プルリクエスト

#### 開発環境のセットアップ

```bash
# リポジトリをフォーク & クローン
git clone https://github.com/YOUR_USERNAME/Paper-CAD.git
cd Paper-CAD

# バックエンドのセットアップ
cd backend
conda env create -f environment.yml
conda activate paper-cad

# フロントエンドのセットアップ
cd ../frontend
npm install
```

#### ブランチの命名規則

- `feat/機能名` - 新機能
- `fix/バグ内容` - バグ修正
- `docs/内容` - ドキュメント
- `refactor/対象` - リファクタリング
- `test/対象` - テスト追加

#### コミットメッセージ

[Conventional Commits](https://www.conventionalcommits.org/) に従ってください：

```
feat: 3D モデルの回転機能を追加
fix: SVG 出力時の座標変換バグを修正
docs: README にクイックスタートを追加
refactor: unfold_engine のコード整理
test: geometry_analyzer のユニットテストを追加
```

#### コードスタイル

**フロントエンド（TypeScript）:**
```bash
npm run format  # Prettier + clang-format
npm test        # テスト実行
```

**バックエンド（Python）:**
```bash
# PEP 8 に準拠
pytest          # テスト実行
```

#### PR の作成

1. 変更を完了したらフォークにプッシュ
2. 本リポジトリに対して PR を作成
3. PR の説明に以下を含める：
   - 変更の概要
   - 関連する Issue 番号（`Closes #123`）
   - テスト結果
   - UI 変更がある場合はスクリーンショット

## 開発ガイドライン

### フロントエンド

- Web Components + CSS Modules を使用
- `chili-*` パッケージ間の依存関係に注意
- TypeScript の strict モードを維持

### バックエンド

- FastAPI のルーター構造に従う
- Pydantic モデルで型定義
- OpenCASCADE 依存の機能は適切にフォールバック

### テスト

- 新機能には対応するテストを追加
- 幾何計算の変更は回帰テストを含める
- CI が通ることを確認してから PR を作成

## ライセンス

コントリビューションは、プロジェクトと同じ [AGPL-3.0](LICENSE) ライセンスの下で提供されます。

## 質問・サポート

- GitHub Issues で質問を投稿
- ディスカッションで一般的な話題を議論

ご協力ありがとうございます！ 🎉
