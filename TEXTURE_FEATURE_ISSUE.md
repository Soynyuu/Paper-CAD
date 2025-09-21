# feat: 展開図SVGエディタにテクスチャパターン塗りつぶし機能を追加

## 📋 概要
展開図SVGエディタにテクスチャ塗りつぶし機能を追加し、選択した面にパターンを適用できるようにする。同時に3Dモデルの対応する面にも簡易表示させる。

## 🎯 目的
- ユーザーが展開図の各面に異なるテクスチャパターンを適用可能にする
- 印刷して組み立てる際の完成イメージを事前に確認できるようにする
- より表現力豊かな紙工作モデルの作成を可能にする

## ✅ 実装タスク

### Phase 1: SVGテクスチャパターン実装（MVP）
- [ ] **テクスチャパターン設定システムの構築**
  - [ ] `public/textures/patterns.json` - パターン定義ファイル作成
  - [ ] `public/textures/` ディレクトリにテクスチャ画像配置
  - [ ] 10種類のプリセットパターン定義（芝生、木目、レンガ、石、布、金属、紙、水、砂、カスタム）

- [ ] **TexturePatternManager モジュール作成**
  - [ ] SVGパターン定義の動的生成・管理機能
  - [ ] SVG defs要素へのパターン注入機能
  - [ ] パターンIDの管理とキャッシュ機構

- [ ] **テクスチャ選択UIの実装**
  - [ ] `stepUnfoldPanel.ts`にテクスチャパレットUI追加
  - [ ] ドロップダウン/パレット形式の選択インターフェース
  - [ ] 面選択→テクスチャ適用のフロー実装
  - [ ] リアルタイムプレビュー機能

- [ ] **SVG-edit統合**
  - [ ] setSvgString実行後のパターンdefs追加
  - [ ] 選択した要素のfill属性動的更新
  - [ ] エクスポート時のパターン定義保持

### Phase 2: 3Dモデル連携
- [ ] **ThreeGeometry拡張**
  - [ ] Multi-Material対応の実装
  - [ ] 面ごとのテクスチャマッピング機能

- [ ] **FaceTextureMapper実装**
  - [ ] 面番号→テクスチャIDのマッピング管理
  - [ ] 3D-2D間の同期機構

- [ ] **テクスチャ読み込み最適化**
  - [ ] TextureLoaderによる非同期読み込み
  - [ ] テクスチャキャッシュ管理

### Phase 3: 拡張機能
- [ ] カスタムテクスチャアップロード機能
- [ ] テクスチャ変換機能（スケール、回転、オフセット）
- [ ] テクスチャプリセットライブラリの拡充
- [ ] パフォーマンス最適化（テクスチャ共有、適切なDispose）

## 🔧 技術詳細

### 必要なモジュール
**既存（追加インストール不要）:**
- `svgedit`: v7.3.8 - SVGエディタ本体
- `three.js`: 3Dテクスチャマッピング

**新規開発:**
- `TexturePatternManager`: SVGパターン定義の管理
- `FaceTextureMapper`: 面番号とテクスチャのマッピング管理
- `TextureSelectionUI`: テクスチャ選択パレット UI

### 実装上の考慮事項

**SVG-editとの統合:**
```javascript
// パターン定義の動的追加例
const defs = svgCanvas.getRootElem().querySelector('defs') ||
             svgCanvas.getRootElem().insertBefore(
               document.createElementNS('http://www.w3.org/2000/svg', 'defs'),
               svgCanvas.getRootElem().firstChild
             );

const pattern = document.createElementNS('http://www.w3.org/2000/svg', 'pattern');
pattern.setAttribute('id', 'grass-pattern');
pattern.setAttribute('patternUnits', 'userSpaceOnUse');
// ... パターン内容設定

// 選択した要素への適用
selectedElement.setAttribute('fill', 'url(#grass-pattern)');
```

**Three.jsテクスチャ適用:**
```javascript
// Multi-Material配列の使用
const materials = faces.map((face, index) => {
  const textureId = faceTextureMapper.getTexture(index);
  if (textureId) {
    const texture = textureLoader.load(`/textures/${textureId}.png`);
    return new MeshLambertMaterial({ map: texture });
  }
  return defaultMaterial;
});

mesh.material = materials;
```

## ⚠️ リスク評価と対策

### 技術的リスク
- **中リスク**: SVG-editの内部API変更による互換性問題
  - 対策: APIラッパー層の実装、バージョン固定
- **低リスク**: Three.jsテクスチャ実装の安定性
  - 対策: 既存の実装パターンを踏襲

### パフォーマンスリスク
- **中リスク**: 大量面へのテクスチャ適用時のメモリ使用量
  - 対策: テクスチャ共有、遅延読み込み、適切なDispose

## 📊 評価結果

### 実装の妥当性: ✅ 実装可能

**判定理由:**
1. 必要な基盤技術（SVG-edit、Three.js）が既に統合されている
2. 面番号システムによる3D-2D同期機構が確立されている
3. 複雑度は中程度で、段階的実装により管理可能
4. 既存のコードベースと整合性が取れている

### イシュードリブン開発の適合性: ✅ 適切

**理由:**
- 明確な要求仕様が定義されている
- 段階的な実装計画により、各フェーズでの成果物が明確
- 既存システムへの影響を最小限に抑えた設計
- テスト可能な単位での機能分割

## 🚀 次のステップ

1. このIssueをGitHubに登録
2. Phase 1のMVP実装から開始
3. 各フェーズ完了時にレビューとフィードバック収集
4. 必要に応じて実装計画を調整

## 📦 関連ファイル
- `packages/chili-ui/src/stepUnfold/stepUnfoldPanel.ts` - メインUI実装
- `packages/chili-three/src/threeGeometry.ts` - 3D表示実装
- `packages/chili-core/src/services/stepUnfoldService.ts` - サービス層
- `public/textures/` - テクスチャ画像格納ディレクトリ（新規作成）

## 🏷️ ラベル
- `enhancement`
- `feature`
- `ui/ux`
- `3d-visualization`