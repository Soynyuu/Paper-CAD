# Backend Refactor Plan

## Goals
- Improve maintainability by splitting large modules and reducing duplication.
- Preserve API behavior and conversion outputs (no functional regressions).
- Make error handling, logging, and temporary file handling consistent.
- Increase test coverage for core pipelines and API boundaries.

## Non-Goals
- Redesign of CAD algorithms or CityGML conversion logic.
- Breaking API changes or payload format changes.
- Performance optimization beyond obvious low-risk wins.

## Current Observations (Targets)
- `backend/api/endpoints.py` is large and mixes HTTP concerns with business logic.
- Upload and temp file handling is duplicated across multiple endpoints.
- Parameter normalization is repeated and partially inconsistent.
- Logging uses `print` and even overrides `builtins.print` in `backend/config.py`.
- `backend/services/plateau_fetcher.py` modifies `sys.path` to import utilities.
- `backend/services/step_processor_old.py` appears unused and increases maintenance cost.
- Test coverage is limited to CityGML streaming components.

## Target Architecture (Proposed)
```
backend/
  api/
    routers/
      step.py
      citygml.py
      plateau.py
      system.py
    dependencies.py
  services/
    step_service.py
    citygml_service.py
    plateau_service.py
  core/
    step_pipeline/
      loaders.py
      analysis.py
      unfolding.py
      layout.py
      exporters.py
  utils/
    temp_files.py
    logging.py
    validation.py
```

## Phased Plan

### Phase 0 - Baseline and Guardrails
- Snapshot current API behavior with a small set of integration tests:
  - `POST /api/step/unfold` (SVG and JSON)
  - `POST /api/step/unfold-pdf`
  - `POST /api/citygml/to-step`
  - One PLATEAU search and convert flow
- Capture representative output artifacts for regression checks.
- Document current environment assumptions (OCCT availability, demo mode).

Exit Criteria:
- Tests can run locally and verify basic success paths.
- Golden files stored for at least one STEP and one CityGML sample.

### Phase 1 - API Layer Separation
- Split `backend/api/endpoints.py` into routers by domain.
- Keep routes identical; only move code and fix imports.
- Extract shared helpers:
  - `save_upload_to_tmpdir()`
  - `cleanup_tmpdir()`
  - `normalize_limit()` / `parse_csv_ids()`
- Centralize HTTPException mapping for known failure cases.

Exit Criteria:
- All endpoints behave the same; no changes in OpenAPI paths or tags.
- No duplicated temp file handling in routers.

### Phase 2 - Service Layer Extraction
- Create service classes for each domain:
  - `StepService` wraps `StepUnfoldGenerator` and export logic.
  - `CityGMLService` wraps `export_step_from_citygml`.
  - `PlateauService` wraps search and fetch workflows.
- Move parameter normalization and validation out of routers into services.
- Ensure services expose pure functions where possible for testing.

Exit Criteria:
- Routers only coordinate HTTP I/O and call services.
- Unit tests added for services with mocked inputs.

### Phase 3 - Step Pipeline Cleanup
- Consolidate repeated parameter propagation between `StepUnfoldGenerator`,
  `SVGExporter`, `PDFExporter`, and `LayoutManager`.
- Introduce a configuration dataclass to carry layout and export options.
- Split `step_processor.py` into smaller modules or a `step_pipeline/` package.
- Delete or archive `backend/services/step_processor_old.py`.

Exit Criteria:
- No manual per-attribute copying in PDF path.
- Smaller, focused modules with clear responsibilities.

### Phase 4 - Plateau and CityGML Integration Cleanup
- Remove `sys.path` mutation in `plateau_fetcher.py` and use package imports.
- Move shared constants and XML parsing helpers to `services/citygml/utils/`.
- Add small unit tests for name matching and mesh utilities.

Exit Criteria:
- No runtime path hacks.
- Plateau logic is testable without HTTP calls (use fixtures/mocks).

### Phase 5 - Logging and Config Standardization
- Replace `print` with standard logging in all backend modules.
- Remove `builtins.print` override; use logger levels for demo/production.
- Introduce a structured config object (Pydantic settings) for ENV, CORS, ports.

Exit Criteria:
- Single logging configuration with consistent formatting.
- Environment configuration is centralized and typed.

## Risks and Mitigations
- Risk: Behavior drift in complex conversion flows.
  - Mitigation: Keep outputs stable with golden file tests.
- Risk: OCCT dependency issues during refactor.
  - Mitigation: Guard OCCT paths and maintain existing 503 behavior.
- Risk: Large file handling regressions.
  - Mitigation: Preserve chunked read/write and temp cleanup patterns.

## Test Strategy
- Unit tests for normalization helpers and services.
- Integration tests for each major endpoint.
- Optional performance smoke tests for large inputs (record timings only).

## Definition of Done
- All phases complete, tests passing, and no API contract changes.
- API endpoints documented and split into routers.
- Service layer isolates domain logic from HTTP concerns.

## 日本語版

## 目的
- 大きなモジュールを分割し、重複を減らして保守性を向上する。
- APIの挙動や変換結果を保持し、機能退行を起こさない。
- エラーハンドリング、ログ、テンポラリ管理を一貫化する。
- コアパイプラインとAPI境界のテストカバレッジを上げる。

## 対象外
- CADアルゴリズムやCityGML変換ロジックの再設計。
- API仕様やレスポンス形式の破壊的変更。
- 低リスクな範囲を超える性能最適化。

## 現状の課題（整理）
- `backend/api/endpoints.py` が巨大でHTTP層と業務ロジックが混在。
- アップロードと一時ファイル処理が複数箇所で重複。
- パラメータ正規化が重複し、挙動が部分的に不統一。
- `backend/config.py` で `print` を上書きしており観測性が不安定。
- `backend/services/plateau_fetcher.py` が `sys.path` を変更している。
- `backend/services/step_processor_old.py` が残存し保守負担に。
- テストが CityGML ストリーミング周辺に偏っている。

## 目標アーキテクチャ（案）
```
backend/
  api/
    routers/
      step.py
      citygml.py
      plateau.py
      system.py
    dependencies.py
  services/
    step_service.py
    citygml_service.py
    plateau_service.py
  core/
    step_pipeline/
      loaders.py
      analysis.py
      unfolding.py
      layout.py
      exporters.py
  utils/
    temp_files.py
    logging.py
    validation.py
```

## フェーズ別計画

### Phase 0 - ベースラインと安全柵
- 現行APIの最小限の統合テストを用意:
  - `POST /api/step/unfold`（SVG/JSON）
  - `POST /api/step/unfold-pdf`
  - `POST /api/citygml/to-step`
  - PLATEAUの検索→変換の一連フロー
- 代表的な出力を保存し、回帰チェック可能にする。
- 実行環境前提（OCCT有無、demoモード）を記録。

Exit Criteria:
- ローカルでテストが実行でき、成功経路を検証できる。
- STEP/CityGMLの少なくとも1件はゴールデンファイルを保存。

### Phase 1 - API層の分離
- `backend/api/endpoints.py` をドメイン単位で分割。
- ルーティングやタグは変更せず、移動とインポート修正のみ。
- 共有ヘルパーを抽出:
  - `save_upload_to_tmpdir()`
  - `cleanup_tmpdir()`
  - `normalize_limit()` / `parse_csv_ids()`
- 既知のエラー変換を共通化。

Exit Criteria:
- OpenAPIのパスやタグが変わらない。
- テンポラリ処理が重複しない。

### Phase 2 - サービス層の抽出
- ドメインごとにサービスを用意:
  - `StepService` が `StepUnfoldGenerator` を統括
  - `CityGMLService` が `export_step_from_citygml` をラップ
  - `PlateauService` が検索と取得処理を担当
- パラメータ正規化とバリデーションをサービス側に移動。
- 可能な限り純粋関数化してテスト容易性を確保。

Exit Criteria:
- ルーターはHTTP I/Oのみを担当。
- サービス層のユニットテストを追加。

### Phase 3 - STEPパイプライン整理
- `StepUnfoldGenerator` と `SVGExporter`/`PDFExporter`/`LayoutManager`
  へのパラメータ伝播を集約。
- レイアウト/出力用の設定データクラスを導入。
- `step_processor.py` を `step_pipeline/` 配下に分割。
- `backend/services/step_processor_old.py` を削除またはアーカイブ。

Exit Criteria:
- PDF経路での手動プロパティコピーが消える。
- 小さく責務の明確なモジュール群になる。

### Phase 4 - PLATEAU/CityGML周辺の整理
- `plateau_fetcher.py` の `sys.path` 依存を除去し正規importに変更。
- 共有定数やXML処理を `services/citygml/utils/` に集約。
- 名称マッチングとメッシュ計算の小さなユニットテストを追加。

Exit Criteria:
- ランタイムのパス操作がなくなる。
- HTTP依存なしでPLATEAUロジックをテスト可能。

### Phase 5 - ログ/設定の標準化
- すべての `print` を標準ロガーへ移行。
- `builtins.print` の上書きを廃止し、ログレベルで抑制。
- 環境設定をPydantic設定などで集中管理。

Exit Criteria:
- 一貫したログフォーマット。
- 環境設定が型付きで集中管理される。

## リスクと対策
- リスク: 変換ロジックの挙動差分。
  - 対策: ゴールデンファイルで出力一致を確認。
- リスク: OCCT依存の切り分けが難しい。
  - 対策: OCCT未導入時の503挙動を維持。
- リスク: 大容量ファイルの取り扱い退行。
  - 対策: 既存のチャンク読み書きとクリーンアップを維持。

## テスト戦略
- 正規化ヘルパーとサービス層のユニットテスト。
- 主要エンドポイントの統合テスト。
- 大容量入力の簡易パフォーマンス計測（タイムスタンプ記録のみ）。

## 完了条件
- 全フェーズが完了し、テストが通り、API契約が変わらない。
- ルーター分割とサービス層分離が終わっている。

## 商用レベル化プラン（追加）

## 目的
- 商用運用に必要な信頼性・セキュリティ・運用性を満たす。
- 期待するSLA/SLOとコスト/性能のバランスを明確化する。
- 事故対応や監視の「運用可能性」を担保する。

## 前提整理（最初に決めること）
- SLA/SLO: 可用性、レスポンスタイム、成功率、最大同時処理数。
- 入力条件: 最大ファイルサイズ、最大処理時間、許容される失敗率。
- データ扱い: アップロードファイルの保持期間、再利用可否、暗号化要件。
- 外部依存: Nominatim/PLATEAUの利用規約とレート制限（商用利用の可否）。

## フェーズ別計画

### Phase A - 可観測性と運用ベースライン
- 構造化ログ（JSON）とログレベル基準の導入。
- リクエストID/ジョブIDの付与、相関ログの整備。
- 主要メトリクス（処理時間、失敗率、ファイルサイズ、OCCTエラー）を収集。
- ダッシュボードとアラート（失敗率/レイテンシ急増）を設定。

Exit Criteria:
- 主要APIのメトリクスが観測でき、障害が通知される。

### Phase B - 信頼性（ジョブ管理と耐障害性）
- 長時間処理を非同期ジョブ化し、キャンセル/再試行を可能にする。
- タイムアウト/最大実行時間/メモリ上限を明確化。
- 入出力の一時ファイル管理を統一し、リークを防ぐ。
- リトライ方針（外部API/一時失敗）と冪等性を定義。

Exit Criteria:
- 長時間処理が安定して実行され、再試行とキャンセルが機能する。

### Phase C - セキュリティとAPI制御
- 認証/認可（APIキー、JWT、IP制限など）を導入。
- レート制限、アップロード制限、入力検証を強化。
- 依存関係の脆弱性スキャン、秘密情報管理を整備。
- CORS/HTTPヘッダの強化と監査ログの整備。

Exit Criteria:
- 主要な攻撃面（過負荷・不正アクセス・入力悪用）が抑制される。

### Phase D - 性能とスケール
- プロファイリングでボトルネックを計測し、改善対象を確定。
- ワーカー数/並列度の調整とキューのスケール戦略を決定。
- 大容量ファイルの性能試験（平均/最悪ケース）を実施。

Exit Criteria:
- 目標SLOを満たす性能が再現可能である。

### Phase E - CI/CDと運用プロセス
- ステージング環境と本番環境の分離。
- 自動テスト（ユニット/統合/回帰）とリリース手順の整備。
- ロールバック手順、障害対応のRunbookを整備。

Exit Criteria:
- 変更が安全にデプロイ可能で、障害時に復旧できる。

### Phase F - データとコンプライアンス
- アップロードデータの保持期間と削除ポリシーを明文化。
- 暗号化（転送/保存）とアクセス制御を実装。
- ライセンスと利用規約の遵守確認（OCCT/外部API）。

Exit Criteria:
- データ取り扱いが明確化され、運用/監査に耐えられる。

## 商用化の最小要件（MVP）
- Phase A + Phase B + Phase C の完了。
- SLOが定義され、監視と通知が動作する。
- 認証/制限/入力検証で基本的なリスクを抑制。

## 完了条件（商用レベル）
- SLO達成を継続的に計測できる。
- 主要障害シナリオに対する復旧手順が整備されている。
- 運用コストと性能要件のバランスが取れている。
