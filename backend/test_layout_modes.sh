#!/bin/bash

# 展開図レイアウトモードのテストスクリプト

echo "=== STEP to SVG Layout Mode Test ==="
echo ""

# テスト用のSTEPファイルパスを設定（実際のファイルパスに変更してください）
STEP_FILE="test_model.step"

# APIエンドポイント
API_URL="http://localhost:8001/api/step/unfold"

# 1. フリーキャンバスモード（デフォルト）
echo "1. フリーキャンバスモード（従来の動的サイズ）"
echo "----------------------------------------"
curl -X POST \
  -F "file=@${STEP_FILE}" \
  -F "layout_mode=canvas" \
  -F "output_format=svg" \
  ${API_URL} \
  -o canvas_mode.svg
echo "✅ canvas_mode.svg を生成しました"
echo ""

# 2. ページモード - A4縦
echo "2. ページモード - A4縦"
echo "----------------------"
curl -X POST \
  -F "file=@${STEP_FILE}" \
  -F "layout_mode=paged" \
  -F "page_format=A4" \
  -F "page_orientation=portrait" \
  -F "output_format=zip" \
  ${API_URL} \
  -o a4_portrait_pages.zip
echo "✅ a4_portrait_pages.zip を生成しました"
echo ""

# 3. ページモード - A3横
echo "3. ページモード - A3横"
echo "----------------------"
curl -X POST \
  -F "file=@${STEP_FILE}" \
  -F "layout_mode=paged" \
  -F "page_format=A3" \
  -F "page_orientation=landscape" \
  -F "output_format=zip" \
  ${API_URL} \
  -o a3_landscape_pages.zip
echo "✅ a3_landscape_pages.zip を生成しました"
echo ""

# 4. ページモード - Letter縦
echo "4. ページモード - Letter縦"
echo "--------------------------"
curl -X POST \
  -F "file=@${STEP_FILE}" \
  -F "layout_mode=paged" \
  -F "page_format=Letter" \
  -F "page_orientation=portrait" \
  -F "output_format=zip" \
  ${API_URL} \
  -o letter_portrait_pages.zip
echo "✅ letter_portrait_pages.zip を生成しました"
echo ""

# 5. ページモード（最初のページのみ取得）
echo "5. ページモード - 最初のページSVG"
echo "---------------------------------"
curl -X POST \
  -F "file=@${STEP_FILE}" \
  -F "layout_mode=paged" \
  -F "page_format=A4" \
  -F "page_orientation=portrait" \
  -F "output_format=svg" \
  ${API_URL} \
  -o first_page_only.svg
echo "✅ first_page_only.svg を生成しました"
echo ""

# 6. JSON形式での取得（ページモード）
echo "6. JSON形式 - ページモード"
echo "-------------------------"
curl -X POST \
  -F "file=@${STEP_FILE}" \
  -F "layout_mode=paged" \
  -F "page_format=A4" \
  -F "page_orientation=portrait" \
  -F "output_format=json" \
  ${API_URL} \
  -o paged_json_response.json
echo "✅ paged_json_response.json を生成しました"
echo ""

# 7. JSON形式での取得（キャンバスモード）
echo "7. JSON形式 - キャンバスモード"
echo "------------------------------"
curl -X POST \
  -F "file=@${STEP_FILE}" \
  -F "layout_mode=canvas" \
  -F "output_format=json" \
  ${API_URL} \
  -o canvas_json_response.json
echo "✅ canvas_json_response.json を生成しました"
echo ""

echo "=== 全てのテストが完了しました ==="
echo ""
echo "生成されたファイル:"
echo "  - canvas_mode.svg         : フリーキャンバスモード"
echo "  - a4_portrait_pages.zip   : A4縦の複数ページ"
echo "  - a3_landscape_pages.zip  : A3横の複数ページ"
echo "  - letter_portrait_pages.zip : Letter縦の複数ページ"
echo "  - first_page_only.svg     : ページモードの最初のページ"
echo "  - paged_json_response.json : ページモードのJSON"
echo "  - canvas_json_response.json : キャンバスモードのJSON"
echo ""
echo "ZIPファイルを解凍して個別のページSVGを確認してください。"