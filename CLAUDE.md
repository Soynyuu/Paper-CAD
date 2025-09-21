# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two integrated projects developed for the 2025 Mitou Junior Program, collectively called Paper-CAD:

1. **chili3d** - Browser-based 3D CAD application (fork of [xiangechen/chili3d](https://github.com/xiangechen/chili3d))
2. **unfold-step2svg** - 3D-to-2D papercraft generation service

Both projects integrate to provide a complete 3D modeling to physical papercraft workflow.

## Common Development Commands

### chili3d (TypeScript/WebAssembly CAD)

```bash
cd chili3d
npm install                 # First-time setup
npm run dev                # Dev server at http://localhost:8080
npm run build             # Production build
npm run build:wasm        # Rebuild WASM (requires cmake)
npm test                  # Run all tests
npm test -- packages/chili-core/test/math.test.ts  # Single test
npm run format            # Format TS and C++ code
npx tsc --noEmit         # Type check
```

### unfold-step2svg (Python/FastAPI Service)

```bash
cd unfold-step2svg
conda env create -f environment.yml    # First-time setup
conda activate unfold-step2svg
python main.py                         # API at http://localhost:8001

# API Testing
curl http://localhost:8001/api/health
curl -X POST -F "file=@model.step" http://localhost:8001/api/step/unfold -o output.svg
```

## High-Level Architecture

### chili3d - Monorepo Structure

**Core Design Principles:**
- Interface-based architecture with 11 npm workspace packages
- WebAssembly integration for native-speed OpenCASCADE operations
- Custom reactive UI system with property decorators

**Key Packages:**
- `chili-core`: Interfaces (IDocument, INode, ICommand) - contract definitions
- `chili-wasm`: OpenCASCADE WASM bindings - geometry engine
- `chili-three`: Three.js visualization - 3D rendering
- `chili-ui`: Custom UI framework with ribbon interface
- `chili`: Main application logic - commands, snapping, steps
- `chili-builder`: Application initialization via builder pattern

**Architectural Patterns:**

1. **Builder Pattern Configuration:**
   ```typescript
   new AppBuilder()
     .useIndexedDB()
     .useWasmOcc()
     .useThree()
     .useUI()
     .build();
   ```

2. **Command Pattern with Undo/Redo:**
   - All user actions are commands in `packages/chili/src/commands/`
   - Categories: `create/`, `modify/`, `measure/`, `application/`
   - Multi-step commands via `MultistepCommand`

3. **Step-Based User Interaction:**
   - Complex operations broken into steps (`packages/chili/src/step/`)
   - Steps handle validation, user input, and state transitions

4. **Service Architecture:**
   - Services registered via `AppBuilder.getServices()`
   - Key services: `CommandService`, `HotkeyService`, `StepUnfoldService`
   - `StepUnfoldService` integrates with unfold-step2svg backend

### unfold-step2svg - Pipeline Architecture

**Processing Pipeline:**
1. **File Loading** (`core/file_loaders.py`) - STEP/BREP parsing
2. **Geometry Analysis** (`core/geometry_analyzer.py`) - Face classification
3. **Unfolding** (`core/unfold_engine.py`) - 3D→2D transformation
4. **Layout** (`core/layout_manager.py`) - Canvas or paged layout
5. **Export** (`core/svg_exporter.py`) - SVG with face numbers

**Service Layer:**
- `StepUnfoldGenerator` in `services/step_processor.py` orchestrates the pipeline
- FastAPI endpoints in `api/endpoints.py`

**Key Features:**
- Dual layout modes: dynamic canvas or fixed pages (A4/A3/Letter)
- Face numbering synchronized with chili3d's 3D display
- Debug file generation in `core/debug_files/` for troubleshooting

## Integration Points

### Backend Service Connection
- chili3d's `StepUnfoldService` calls unfold-step2svg at https://backend-diorama.soynyuu.com
- STEP export from chili3d → Processing in unfold-step2svg → SVG import back
- Face numbers synchronized between 3D view and 2D papercraft

### Face Numbering System
- chili3d: 3D face numbers via Three.js sprites (`packages/chili-three/src/faceNumberDisplay.ts`)
- unfold-step2svg: 2D face numbers in SVG (`core/svg_exporter.py`)
- Both use normal vector analysis for consistent numbering

## Critical Implementation Details

### chili3d Specifics
- **WASM Memory Management**: Use `gc()` helper for OpenCASCADE objects
- **Document Version**: 0.6 - increment when changing serialization
- **Reactive UI**: Custom decorators for data binding in `.module.css` files
- **Build Tool**: Rspack (faster than Webpack)
- **Testing**: Jest with ESM support, CSS modules mocked

### unfold-step2svg Specifics
- **OpenCASCADE Version**: 7.9.0 via pythonocc-core
- **Max Faces**: Limited to 20 faces per model for performance
- **Scale Factor**: Default 10.0 for mm to SVG units
- **Error Recovery**: Failed operations save debug STEP files

## Working with WASM (chili3d)

```javascript
// Always await initialization
await initWasm();

// Memory management pattern
const shape = createShape();
try {
  // Use shape
} finally {
  gc(shape);  // Manual cleanup
}
```

## API Endpoints (unfold-step2svg)

```bash
POST /api/step/unfold
  file: STEP file (required)
  return_face_numbers: bool (default: true)
  layout_mode: "canvas" | "paged"
  page_format: "A4" | "A3" | "Letter"
  scale_factor: float (default: 10.0)
```

## Testing Strategies

### chili3d
```bash
npm test                     # All tests
npm test -- --watch         # Watch mode
npm test -- path/to/test.ts # Specific test
```

### unfold-step2svg
```bash
bash test_face_numbers.sh    # Face numbering
bash test_layout_modes.sh    # Layout modes
python test_*.py            # Python unit tests
```

## Key File Locations

### chili3d Configuration
- `rspack.config.js` - Build configuration
- `packages/*/src/` - Package source code
- `cpp/src/` - C++ OpenCASCADE bindings

### unfold-step2svg Configuration
- `environment.yml` - Conda dependencies
- `core/` - Processing pipeline modules
- `api/config.py` - Server configuration

## Commit Message Guidelines

### 基本フォーマット

```
<タイプ>(<スコープ>): <概要>

[本文]

[フッター]
```

### タイプ一覧

- `feat` / `機能追加`: 新機能の追加
- `fix` / `修正`: バグ修正
- `refactor` / `リファクタリング`: 機能に影響しないコード改善
- `perf` / `性能改善`: パフォーマンス向上
- `style` / `スタイル`: フォーマット、セミコロンの追加など
- `test` / `テスト`: テストの追加・修正
- `docs` / `ドキュメント`: ドキュメントのみの変更
- `build` / `ビルド`: ビルドシステムや依存関係の変更
- `ci` / `CI`: CI/CD設定の変更
- `chore` / `雑務`: その他の変更

### スコープ一覧

#### chili3d パッケージ
- `chili-core`: コアインターフェース定義
- `chili-wasm`: OpenCASCADE WASMバインディング
- `chili-three`: Three.js 3D表示
- `chili-ui`: UIフレームワーク
- `chili`: メインアプリケーションロジック
- `chili-builder`: アプリケーション初期化
- `chili-geo`: ジオメトリユーティリティ
- `chili-storage`: ストレージ管理
- `chili-vis`: ビジュアライゼーション
- `chili-controls`: コントロール
- `chili-web`: Web固有機能

#### unfold-step2svg モジュール
- `api`: FastAPIエンドポイント
- `core`: 処理パイプライン
- `models`: データモデル
- `services`: サービス層
- `layout`: レイアウトマネージャー
- `svg`: SVGエクスポート

#### 共通スコープ
- `root`: リポジトリ全体
- `deps`: 依存関係
- `config`: 設定ファイル
- `*`: 複数パッケージ（詳細を本文に記載）

### コミットメッセージ例

#### 単一パッケージの変更
```
feat(chili-three): 面番号表示機能を追加

- Three.jsのSpriteを使用して3D空間に面番号を表示
- 面の法線ベクトルに基づいて番号を配置
- ユーザーが表示/非表示を切り替え可能

Closes #123
```

```
修正(unfold-step2svg/core): 展開図生成時のメモリリークを解消

OpenCASCADEオブジェクトのガベージコレクションが
適切に実行されていなかった問題を修正。
処理後に明示的にgc()を呼び出すように変更。
```

#### 複数パッケージの変更
```
feat(*): ペーパークラフト統合機能を実装

影響パッケージ:
- chili: StepUnfoldServiceの追加
- chili-ui: 展開図ボタンの追加
- chili-three: 面番号表示の実装

バックエンドと連携してSTEP→SVG変換を実現

Breaking Change: ICommandインターフェースを変更
```

#### リファクタリング
```
リファクタリング(chili-wasm): メモリ管理パターンを統一

全てのOpenCASCADEオブジェクトでRAIIパターンを適用:
- try-finallyブロックで確実にgc()を実行
- ヘルパー関数withOccObject()を追加
- メモリリークのリスクを大幅に削減
```

#### ビルド・CI関連
```
build(chili3d): rspackの設定を最適化

- チャンクサイズを調整（500KB → 200KB）
- Tree shakingを有効化
- ビルド時間を40%短縮
```

```
ci(root): GitHub Actionsでモノレポ対応のテストを追加

- 変更されたパッケージのみテストを実行
- 依存パッケージも自動的にテスト対象に含める
- テスト実行時間を60%削減
```

### Breaking Changeの記述

Breaking Changeがある場合は、フッターに明記：

```
feat(chili-core): IDocumentインターフェースを刷新

新しいバージョニングシステムを導入し、
下位互換性を保ちながら段階的な移行を可能に。

BREAKING CHANGE: IDocument.save()の引数が変更されました。
旧: save(path: string)
新: save(options: SaveOptions)

移行方法:
doc.save(path) → doc.save({ path })
```

### 日本語と英語の使い分け

- **日本語推奨**: 概要、本文の説明
- **英語推奨**: タイプ、スコープ、Breaking Change表記
- **混在OK**: 技術用語は英語のまま使用可能

```
修正(chili-three): WebGLコンテキストロスト時のリカバリー処理を改善

WebGLRenderingContextのcontextlostイベントを適切に
ハンドリングし、自動的に再初期化を行うように修正。
これによりタブ切り替え時の描画エラーが解消される。
```

### コミット本文の書き方

1. **なぜ変更したか**を最初に説明
2. **何を変更したか**を具体的に記述
3. **影響範囲**がある場合は明記
4. 関連Issue/PRは`Refs #123`や`Closes #456`で参照

### モノレポ特有の注意点

1. **スコープは必須**: どのパッケージへの変更か明確にする
2. **依存関係の変更**: 複数パッケージに影響する場合は`*`スコープを使用
3. **バージョニング**: package.jsonの変更時はセマンティックバージョニングに従う
4. **CI/CDへの配慮**: 変更がビルド・デプロイに与える影響を考慮

## Development Workflow (開発ワークフロー)

### Issue駆動開発

コード追加・修正を行う前に、必ず以下の手順を実施：

1. **GitHubでIssueを作成**
   ```markdown
   タイトル: [feat/fix/refactor] 作業内容の簡潔な説明

   ## 概要
   実装する機能や修正する問題の説明

   ## 実装内容
   - [ ] タスク1
   - [ ] タスク2
   - [ ] タスク3

   ## 影響範囲
   - 影響を受けるパッケージ/モジュール
   - 依存関係の変更有無
   ```

2. **ブランチの作成**
   ```bash
   # Issue番号を含むブランチ名を作成
   git checkout -b feature/#123-add-face-numbers
   git checkout -b fix/#124-memory-leak
   git checkout -b refactor/#125-optimize-rendering
   ```

3. **ブランチ命名規則**
   - `feature/#<issue番号>-<簡潔な説明>`: 新機能
   - `fix/#<issue番号>-<簡潔な説明>`: バグ修正
   - `refactor/#<issue番号>-<簡潔な説明>`: リファクタリング
   - `docs/#<issue番号>-<簡潔な説明>`: ドキュメント
   - `test/#<issue番号>-<簡潔な説明>`: テスト追加・修正

### 作業フロー

1. **Issue作成** → 作業内容と目的を明確化
2. **ブランチ作成** → mainブランチから分岐
3. **実装** → Issueのタスクリストに沿って開発
4. **コミット** → 上記のコミットメッセージガイドラインに従う
5. **プルリクエスト** → Issue番号を参照（`Closes #123`）
6. **マージ** → レビュー後にmainブランチへ

### プルリクエストのテンプレート

```markdown
## 概要
Closes #<issue番号>

実装内容の簡潔な説明

## 変更内容
- 主要な変更点1
- 主要な変更点2
- 主要な変更点3

## 影響範囲
- [ ] chili3d
  - [ ] chili-core
  - [ ] chili-three
  - [ ] その他: ___
- [ ] unfold-step2svg
  - [ ] api
  - [ ] core
  - [ ] その他: ___

## テスト
- [ ] ユニットテストを追加/更新
- [ ] 手動テストを実施
- [ ] ビルドが成功することを確認

## スクリーンショット（UIの変更がある場合）
変更前：
変更後：

## チェックリスト
- [ ] コミットメッセージガイドラインに従った
- [ ] 適切なIssueを参照している
- [ ] Breaking Changeがある場合は明記した
- [ ] ドキュメントを更新した（必要な場合）
```

### Claude Code使用時の注意

Claude Codeで作業を依頼する際は、以下を伝えてください：

1. **作業開始時**: 「Issue #123を作成してブランチを切って作業して」
2. **ブランチ名**: 自動的にIssue番号を含む適切な名前を生成します
3. **コミット時**: Issue番号を自動的にコミットメッセージに含めます
4. **PR作成時**: Issueを自動的に参照し、上記テンプレートを使用します

### 例: Claude Codeへの指示

```
「面番号表示機能を追加したい。Issue作成してブランチ切って作業して」

→ Claude Codeが自動的に:
1. Issue「[feat] 面番号表示機能の追加」を作成
2. ブランチ「feature/#1-add-face-numbers」を作成
3. 実装を進める
4. コミット「feat(chili-three): 面番号表示機能を追加 (#1)」
5. PR作成時にIssue #1を参照
```

## License Notes
- chili3d: AGPL-3.0 (inherited from fork, commercial licensing available)
- unfold-step2svg: MIT License