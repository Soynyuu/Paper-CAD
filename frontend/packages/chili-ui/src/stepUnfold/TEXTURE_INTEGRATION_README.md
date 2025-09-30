# テクスチャ機能統合ガイド

## 概要

このドキュメントでは、展開図SVGエディタにテクスチャパターン塗りつぶし機能を統合する方法を説明します。

## 実装済みコンポーネント

### 1. TexturePatternManager (`texturePatternManager.ts`)

- SVGパターン定義の管理
- パターンのSVG要素への注入
- 国際化対応のパターン名・説明の取得

### 2. TextureSelectionUI (`textureSelectionUI.ts`)

- テクスチャ選択用のUIコンポーネント
- カテゴリごとのパターン表示
- プレビュー機能
- 適用/クリアボタン

### 3. パターン定義 (`public/textures/patterns.json`)

- 10種類のテクスチャパターン定義
- カテゴリ分け（自然、素材、建築、カスタム）
- SVGパターン設定

## StepUnfoldPanelへの統合方法

### 1. インポートの追加

```typescript
import { TextureSelectionUI } from "./textureSelectionUI";
import { TexturePatternManager } from "./texturePatternManager";
```

### 2. プロパティの追加

```typescript
export class StepUnfoldPanel extends HTMLElement {
    // ... 既存のプロパティ ...
    private _textureSelectionUI: TextureSelectionUI | null = null;
    private _texturePatternManager: TexturePatternManager | null = null;
    private _textureButton: HTMLButtonElement;
    private _textureUIVisible: boolean = false;
```

### 3. コンストラクタでの初期化

```typescript
constructor(app: IApplication) {
    // ... 既存のコード ...

    // テクスチャボタンの作成
    this._textureButton = button({
        textContent: "🎨 " + I18n.translate("stepUnfold.texture"),
        className: style.textureButton,
    });

    // テクスチャ選択UIの作成
    this._textureSelectionUI = new TextureSelectionUI({
        onPatternApplied: this._handlePatternApplied.bind(this),
        onPatternRemoved: this._handlePatternRemoved.bind(this),
    });

    // パターンマネージャーの取得
    this._texturePatternManager = this._textureSelectionUI.getPatternManager();

    // ボタンクリックハンドラ
    this._textureButton.onclick = () => this._toggleTextureUI();
}
```

### 4. SVG表示時のパターンマネージャー初期化

```typescript
private async _displaySVG(svgContent: string) {
    // ... 既存のコード（SVG-edit初期化） ...

    // SVG-editの準備完了後
    this._svgEditor.ready(() => {
        // ... 既存のコード ...

        // パターンマネージャーの初期化
        if (this._texturePatternManager && this._svgEditor.svgCanvas) {
            const svgRoot = this._svgEditor.svgCanvas.getRootElem();
            if (svgRoot) {
                this._texturePatternManager.initializeSvgDefs(svgRoot);
            }
        }

        // 選択変更イベントのリスニング
        this._setupTextureSelectionEvents();
    });
}
```

### 5. 選択イベントの処理

```typescript
private _setupTextureSelectionEvents() {
    if (!this._svgEditor || !this._svgEditor.svgCanvas) return;

    const canvas = this._svgEditor.svgCanvas;

    // 選択変更時
    canvas.bind("selected", () => {
        const selectedElements = canvas.getSelectedElems();
        const elementIds = selectedElements
            .filter(elem => elem && elem.id)
            .map(elem => elem.id);

        // テクスチャUIに選択要素を通知
        if (this._textureSelectionUI) {
            this._textureSelectionUI.setSelectedElements(elementIds);
        }
    });
}
```

### 6. パターン適用/削除ハンドラ

```typescript
private async _handlePatternApplied(elementId: string, patternId: string) {
    if (!this._svgEditor || !this._svgEditor.svgCanvas || !this._texturePatternManager) {
        return;
    }

    const canvas = this._svgEditor.svgCanvas;
    const svgRoot = canvas.getRootElem();
    const element = svgRoot.querySelector(`#${elementId}`);

    if (element instanceof SVGElement) {
        await this._texturePatternManager.applyPatternToElement(element, patternId);
    }
}

private _handlePatternRemoved(elementId: string) {
    if (!this._svgEditor || !this._svgEditor.svgCanvas || !this._texturePatternManager) {
        return;
    }

    const canvas = this._svgEditor.svgCanvas;
    const svgRoot = canvas.getRootElem();
    const element = svgRoot.querySelector(`#${elementId}`);

    if (element instanceof SVGElement) {
        this._texturePatternManager.removePatternFromElement(element);
    }
}
```

### 7. UIトグル機能

```typescript
private _toggleTextureUI() {
    this._textureUIVisible = !this._textureUIVisible;

    if (this._textureSelectionUI) {
        if (this._textureUIVisible) {
            this._textureSelectionUI.style.display = "block";
            this._textureButton.classList.add(style.active);
        } else {
            this._textureSelectionUI.style.display = "none";
            this._textureButton.classList.remove(style.active);
        }
    }
}
```

### 8. レンダリングメソッドの更新

```typescript
private _render() {
    this.append(
        div(
            { className: style.root },
            div(
                { className: style.controls },
                div(
                    { className: style.buttonRow },
                    this._showFaceNumbersButton,
                    this._layoutModeButton,
                    this._textureButton  // テクスチャボタンを追加
                ),
                // ... 既存のコントロール ...
            ),
            // テクスチャ選択UIを追加（初期は非表示）
            this._textureSelectionUI &&
                div({ style: { display: "none" } }, this._textureSelectionUI),
            this._svgWrapper,
        ),
    );
}
```

## 国際化対応

以下のキーを `chili-core/src/i18n/` に追加：

```typescript
// ja.ts
{
    "stepUnfold.texture": "テクスチャ",
    "stepUnfold.texturePattern": "テクスチャパターン",
    "stepUnfold.textureSelection": "テクスチャ選択",
    "stepUnfold.selectPattern": "パターンを選択...",
    "stepUnfold.noPatternSelected": "パターンが選択されていません",
    "stepUnfold.applyTexture": "適用",
    "stepUnfold.clearTexture": "クリア",
    "stepUnfold.textureApplied": "テクスチャを適用しました",
    "stepUnfold.textureCleared": "テクスチャをクリアしました"
}

// en.ts
{
    "stepUnfold.texture": "Texture",
    "stepUnfold.texturePattern": "Texture Pattern",
    "stepUnfold.textureSelection": "Texture Selection",
    "stepUnfold.selectPattern": "Select pattern...",
    "stepUnfold.noPatternSelected": "No pattern selected",
    "stepUnfold.applyTexture": "Apply",
    "stepUnfold.clearTexture": "Clear",
    "stepUnfold.textureApplied": "Texture applied",
    "stepUnfold.textureCleared": "Texture cleared"
}
```

## スタイルの追加

`stepUnfoldPanel.module.css`に以下を追加：

```css
.textureButton {
    padding: 4px 8px;
    border-radius: 4px;
    background: var(--chili-background-secondary);
    border: 1px solid var(--chili-border);
    cursor: pointer;
    transition: all 0.2s;
}

.textureButton:hover {
    background: var(--chili-primary-hover);
}

.textureButton.active {
    background: var(--chili-primary);
    color: white;
}
```

## テスト方法

1. 開発サーバーを起動

    ```bash
    npm run dev
    ```

2. 3Dモデルをロードまたは作成

3. 展開図パネルでSVGを生成

4. テクスチャボタンをクリックしてUIを表示

5. SVG要素を選択してパターンを適用

## 次のステップ

### Phase 2: 3Dモデル連携

- Three.jsマテリアルへのテクスチャ適用
- 面番号を使った3D-2D同期

### Phase 3: 拡張機能

- カスタムテクスチャのアップロード
- テクスチャの変換機能（スケール、回転）
- より多くのプリセットパターン

## トラブルシューティング

### パターンが表示されない

- `/public/textures/patterns.json`が正しく配置されているか確認
- テクスチャ画像ファイル（grass.png、wood.png等）が存在するか確認

### SVG-editとの統合エラー

- SVG-editが完全に初期化されてからパターンマネージャーを初期化する
- `ready()`コールバック内で処理を行う

### パフォーマンス問題

- 大きなテクスチャ画像は事前に最適化する
- 使用されなくなったパターンは`clearPatterns()`でクリーンアップ
