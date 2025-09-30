#!/bin/bash

# 面番号機能テスト用スクリプト

echo "面番号機能のテストを開始します..."

# デバッグファイルから最初のSTEPファイルを使用
STEP_FILE=$(ls core/debug_files/*.step 2>/dev/null | head -1)

if [ -z "$STEP_FILE" ]; then
    echo "エラー: テスト用STEPファイルが見つかりません"
    exit 1
fi

echo "使用するファイル: $STEP_FILE"

# サーバーが起動しているか確認
curl -s http://localhost:8001/api/health > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "エラー: サーバーが起動していません"
    echo "別のターミナルで 'python main.py' を実行してください"
    exit 1
fi

# STEPファイルをアップロードして展開図を生成
OUTPUT_FILE="test_with_face_numbers.svg"
echo "展開図を生成中..."

curl -X POST \
  -F "file=@$STEP_FILE" \
  http://localhost:8001/api/step/unfold \
  -o "$OUTPUT_FILE" \
  -s

if [ $? -eq 0 ] && [ -f "$OUTPUT_FILE" ]; then
    echo "✅ 成功: $OUTPUT_FILE が生成されました"
    echo ""
    echo "SVGファイルに面番号が含まれているか確認中..."
    
    # SVGファイル内に face-number クラスが含まれているか確認
    if grep -q "face-number" "$OUTPUT_FILE"; then
        echo "✅ 面番号が検出されました!"
        
        # 面番号の数をカウント
        COUNT=$(grep -o 'class="face-number"' "$OUTPUT_FILE" | wc -l)
        echo "   面番号の数: $COUNT"
    else
        echo "⚠️  面番号が見つかりません"
    fi
    
    echo ""
    echo "ブラウザで $OUTPUT_FILE を開いて確認してください"
else
    echo "❌ エラー: 展開図の生成に失敗しました"
    exit 1
fi