# Cloudflare Pages デプロイ手順

## 方法1: Cloudflareダッシュボードから手動でプロジェクトを作成

1. [Cloudflareダッシュボード](https://dash.cloudflare.com/)にログイン
2. 左メニューから「Pages」を選択
3. 「プロジェクトを作成」をクリック
4. 以下のいずれかを選択：
    - **GitHubと連携**: GitHubリポジトリを選択して自動デプロイ設定
    - **直接アップロード**: ローカルビルドをアップロード

### GitHub連携の場合（推奨）

- リポジトリ: `Soynyuu/chili3d`を選択
- ブランチ: `main`または`ui-design-system-improvement`
- ビルド設定:
    - ビルドコマンド: `npm run build`
    - ビルド出力ディレクトリ: `dist`
    - 環境変数: 不要

### 直接アップロードの場合

```bash
# ビルド
npm run build

# Cloudflareダッシュボードでプロジェクトを作成後
npx wrangler pages deploy dist --project-name [作成したプロジェクト名]
```

## 方法2: Wrangler CLIでのデプロイ（プロジェクト作成後）

プロジェクトがCloudflareダッシュボードで作成された後:

```bash
# 通常のデプロイ
npm run deploy

# ステージング環境へのデプロイ
npm run deploy:staging

# 本番環境へのデプロイ
npm run deploy:production

# ローカルプレビュー
npm run preview
```

## カスタムドメインの設定

1. Cloudflare Pagesプロジェクトダッシュボードへ移動
2. 「カスタムドメイン」タブを選択
3. ドメインを追加（例: `chili3d.com`）
4. DNSレコードが自動的に設定される

## 環境変数（必要な場合）

プロジェクトの設定 > 環境変数から以下を設定：

- バックエンドURL: `http://153.126.191.72:8001`（既にコードに埋め込み済み）

## トラブルシューティング

### "Project not found"エラーの場合

- Cloudflareダッシュボードで先にプロジェクトを作成
- または、GitHub連携を使用

### ビルドサイズの警告

- 現在のビルドサイズは大きいですが、Cloudflare Pagesは100MBまでサポート
- WASMファイル（14.7MB）とフォントファイル（9.3MB）が主な要因

### デプロイ制限

- Cloudflare Pages無料プラン: 月500デプロイまで
- ファイルサイズ制限: 25MB/ファイル、合計100MB
