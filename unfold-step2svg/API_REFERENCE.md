# unfold-step2svg API Reference

STEP ソリッドモデル（.step/.stp）を高精度な展開図（SVG）へ変換する FastAPI。

## Base URL

```
http://localhost:8001
```

## OpenAPI Docs

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`

## Authentication

不要（現状パブリック）。

## Conventions

- リクエストは `multipart/form-data`（ファイルアップロード）
- 成功時は `image/svg+xml`（SVGファイル）または `application/json`（JSON）
- エラー時は `application/json`（`detail` を含む）

---

## Endpoints

### 1) POST /api/step/unfold — STEP→SVG/JSON 変換

STEP ファイルを受け取り、展開図（SVG）を生成します。

Request

- Content-Type: `multipart/form-data`
- Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `file` | File | Yes | — | STEP ファイル（.step/.stp） |
| `output_format` | string | No | `svg` | `svg`=SVGを返却、`json`=JSONで返却 |
| `return_face_numbers` | boolean | No | `true` | 面番号を JSON レスポンスに含めるか |
| `layout_mode` | string | No | `canvas` | `canvas` または `paged` |
| `page_format` | string | No | `A4` | `A4`, `A3`, `Letter`（`paged`時に有効） |
| `page_orientation` | string | No | `portrait` | `portrait` or `landscape`（`paged`時に有効） |
| `scale_factor` | number | No | `10.0` | 図の縮尺倍率（例: 150=1/150） |

Response — SVG

- Status: `200 OK`
- Content-Type: `image/svg+xml`
- Headers:
  - `X-Layout-Mode`: `canvas` or `paged`
  - `X-Page-Format`: `A4`/`A3`/`Letter`（`paged`時）
  - `X-Page-Orientation`: `portrait`/`landscape`（`paged`時）
  - `X-Page-Count`: `1+`（`paged`時）

Response — JSON（`output_format=json`）

```json
{
  "svg_content": "<svg ...>...</svg>",
  "stats": {
    "page_count": 1,
    "layout_mode": "canvas"
  },
  "face_numbers": [
    { "id": 1, "x": 123.4, "y": 56.7 },
    { "id": 2, "x": 223.4, "y": 86.7 }
  ]
}
```

Errors

| Status | detail |
|--------|--------|
| 400 | `STEPファイル（.step/.stp）のみ対応です。` |
| 400 | `STEPファイルの読み込みに失敗しました。` |
| 500 | `予期しないエラー: ...` |
| 503 | `OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。` |

Examples

— SVG を保存

```bash
curl -X POST \
  -F "file=@example.step" \
  "http://localhost:8001/api/step/unfold" \
  -o output.svg
```

— JSON で取得（面番号込み）

```bash
curl -X POST \
  -F "file=@example.step" \
  -F "output_format=json" \
  -F "return_face_numbers=true" \
  "http://localhost:8001/api/step/unfold" | jq .
```

— ページレイアウト（A3 横）で SVG

```bash
curl -X POST \
  -F "file=@example.step" \
  -F "layout_mode=paged" \
  -F "page_format=A3" \
  -F "page_orientation=landscape" \
  "http://localhost:8001/api/step/unfold" -o paged.svg
```

---

### 2) GET /api/health — ヘルスチェック

サービス状態と機能を返します。

Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "opencascade_available": true,
  "supported_formats": ["step", "stp", "brep"],
  "features": {
    "step_to_svg_unfold": true,
    "face_numbering": true,
    "multi_page_layout": true,
    "canvas_layout": true,
    "paged_layout": true
  }
}
```

---

## Request Models（参考）

一部の値は内部デフォルトとして `BrepPapercraftRequest` にまとめられます。

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scale_factor` | float | 10.0 | スケールファクター |
| `units` | string | "mm" | 単位（将来拡張） |
| `max_faces` | integer | 20 | 最大面数（将来拡張） |
| `curvature_tolerance` | float | 0.1 | 曲率許容値（将来拡張） |
| `tab_width` | float | 5.0 | タブ幅（将来拡張） |
| `min_face_area` | float | 1.0 | 最小面積（将来拡張） |
| `unfold_method` | string | "planar" | 展開アルゴリズム（将来拡張） |
| `show_scale` | boolean | true | スケール表示（将来拡張） |
| `show_fold_lines` | boolean | true | 折り線表示（将来拡張） |
| `show_cut_lines` | boolean | true | 切り線表示（将来拡張） |

## Notes

- サポート形式: `.step`/`.stp`
- 出力: SVG（ファイル）/ JSON（文字列）
- OCCT が未導入の場合は 503 を返すか、一部機能が制限されます
- 一時ファイルはサーバ側で管理されます

— Made with ❤️ by the unfold-step2svg team

