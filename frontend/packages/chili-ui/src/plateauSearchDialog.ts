// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, label } from "chili-controls";
import { DialogResult, I18n, IApplication } from "chili-core";
import style from "./dialog.module.css";

export interface PlateauSearchOptions {
    query: string;
    radius: number;
    buildingLimit: number;
    autoReproject: boolean;
    mergeBuildingParts: boolean;
    searchMode: "distance" | "name" | "hybrid";
    nameFilter?: string;
}

export class PlateauSearchDialog {
    private constructor() {}

    static show(
        app: IApplication,
        callback?: (result: DialogResult, options?: PlateauSearchOptions) => void,
    ) {
        const dialog = document.createElement("dialog");
        document.body.appendChild(dialog);

        // State for form inputs
        let query = "";
        let searchType: "facility" | "address" = "facility"; // New: 検索タイプ
        let radiusMeters = 100; // ~100m default (in meters)
        let radius = 0.001; // degrees
        let autoReproject = true; // 常にtrue（ユーザーには非表示）
        let mergeBuildingParts = false;

        // Create form inputs
        const queryInput = input({
            type: "text",
            placeholder: '例: "東京駅", "渋谷スクランブルスクエア"',
            style: {
                width: "100%",
                padding: "8px",
                marginTop: "8px",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                fontSize: "var(--font-size-sm)",
            },
            oninput: (e) => {
                query = (e.target as HTMLInputElement).value;
                // エラー表示をクリア
                if (errorContainer) {
                    errorContainer.style.display = "none";
                }
            },
        });

        // ヒントテキスト（動的に変更可能）
        const hintText = div(
            {
                style: {
                    fontSize: "var(--font-size-xs)",
                    color: "var(--neutral-600)",
                    marginTop: "4px",
                },
            },
            "💡 ヒント: 施設名の方が精度が高くなります",
        );

        // インラインエラー表示用コンテナ
        const errorContainer = div({
            style: {
                display: "none",
                padding: "8px 12px",
                marginTop: "8px",
                backgroundColor: "#fee2e2",
                border: "1px solid #dc2626",
                borderRadius: "var(--radius-sm)",
                color: "#dc2626",
                fontSize: "var(--font-size-sm)",
            },
        });

        function showInlineError(message: string) {
            errorContainer.textContent = `⚠️ ${message}`;
            errorContainer.style.display = "block";
            setTimeout(() => {
                errorContainer.style.display = "none";
            }, 5000);
        }

        // 検索タイプラジオボタン
        const facilityRadio = input({
            type: "radio",
            name: "searchType",
            value: "facility",
            checked: true,
            style: { cursor: "pointer", marginRight: "8px" },
            onchange: () => {
                searchType = "facility";
                queryInput.placeholder = '例: "東京駅", "渋谷スクランブルスクエア"';
                hintText.textContent = "💡 ヒント: 施設名で検索すると、建物名マッチングで精度が向上します";
            },
        });

        const addressRadio = input({
            type: "radio",
            name: "searchType",
            value: "address",
            style: { cursor: "pointer", marginRight: "8px" },
            onchange: () => {
                searchType = "address";
                queryInput.placeholder = '例: "東京都千代田区丸の内1-9-1"';
                hintText.textContent = "💡 ヒント: 住所検索では、最も近い建物を距離で判定します";
            },
        });

        // 検索半径スライダー（メートル表記）
        const radiusLabel = label(
            {
                style: {
                    fontWeight: "var(--font-weight-medium)",
                    color: "var(--primary-color)",
                    fontSize: "var(--font-size-sm)",
                },
            },
            "100m",
        );

        const radiusSlider = input({
            type: "range",
            min: "50",
            max: "500",
            value: "100",
            step: "10",
            style: {
                width: "100%",
                marginTop: "8px",
                accentColor: "var(--primary-color)",
                cursor: "pointer",
            },
            oninput: (e) => {
                radiusMeters = parseInt((e.target as HTMLInputElement).value);
                radiusLabel.textContent = `${radiusMeters}m`;
                radius = radiusMeters / 111000; // メートル→度数に変換（概算）
            },
        });

        // 詳細設定用チェックボックス（アコーディオン内に配置）
        const mergeBuildingPartsCheckbox = input({
            type: "checkbox",
            checked: false,
            style: {
                cursor: "pointer",
            },
            onchange: (e) => {
                mergeBuildingParts = (e.target as HTMLInputElement).checked;
            },
        });

        // 詳細設定アコーディオン
        let showAdvanced = false;
        const advancedToggle = button({
            textContent: "▼ 詳細設定",
            style: {
                background: "none",
                border: "none",
                color: "var(--primary-color)",
                cursor: "pointer",
                fontSize: "var(--font-size-sm)",
                padding: "4px 0",
                textAlign: "left",
            },
            onclick: () => {
                showAdvanced = !showAdvanced;
                advancedToggle.textContent = showAdvanced ? "▲ 詳細設定" : "▼ 詳細設定";
                advancedContainer.style.display = showAdvanced ? "block" : "none";
            },
        });

        const advancedContainer = div(
            {
                style: {
                    display: "none",
                    marginTop: "12px",
                    padding: "12px",
                    backgroundColor: "var(--neutral-50)",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                },
            },
            div(
                {
                    style: {
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                    },
                },
                mergeBuildingPartsCheckbox,
                label(
                    {
                        style: {
                            fontSize: "var(--font-size-sm)",
                            cursor: "pointer",
                        },
                        onclick: () => {
                            mergeBuildingPartsCheckbox.checked = !mergeBuildingPartsCheckbox.checked;
                            mergeBuildingParts = mergeBuildingPartsCheckbox.checked;
                        },
                    },
                    "建物パーツを結合（詳細保持優先: OFF推奨）",
                ),
            ),
        );

        const content = div(
            {
                style: {
                    minWidth: "450px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                },
            },
            // 検索タイプ選択
            div(
                {},
                label(
                    {
                        style: {
                            fontWeight: "var(--font-weight-medium)",
                            fontSize: "var(--font-size-sm)",
                            color: "var(--foreground-color)",
                            display: "block",
                            marginBottom: "12px",
                        },
                    },
                    "検索タイプ *",
                ),
                div(
                    {
                        style: {
                            display: "flex",
                            flexDirection: "column",
                            gap: "12px",
                            padding: "12px",
                            backgroundColor: "var(--neutral-50)",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--border-color)",
                        },
                    },
                    div(
                        {
                            style: {
                                display: "flex",
                                alignItems: "flex-start",
                                gap: "8px",
                            },
                        },
                        facilityRadio,
                        div(
                            {
                                style: {
                                    flex: "1",
                                    cursor: "pointer",
                                },
                                onclick: () => {
                                    facilityRadio.checked = true;
                                    facilityRadio.dispatchEvent(new Event("change"));
                                },
                            },
                            label(
                                {
                                    style: {
                                        fontSize: "var(--font-size-sm)",
                                        fontWeight: "var(--font-weight-medium)",
                                        display: "block",
                                        cursor: "pointer",
                                    },
                                },
                                "📍 施設名で検索",
                            ),
                            div(
                                {
                                    style: {
                                        fontSize: "var(--font-size-xs)",
                                        color: "var(--neutral-600)",
                                        marginTop: "2px",
                                    },
                                },
                                "建物の名前がわかる場合（推奨）",
                            ),
                            div(
                                {
                                    style: {
                                        fontSize: "var(--font-size-xs)",
                                        color: "var(--neutral-500)",
                                        marginTop: "2px",
                                        fontStyle: "italic",
                                    },
                                },
                                '例: "東京駅", "渋谷スクランブルスクエア"',
                            ),
                        ),
                    ),
                    div(
                        {
                            style: {
                                display: "flex",
                                alignItems: "flex-start",
                                gap: "8px",
                            },
                        },
                        addressRadio,
                        div(
                            {
                                style: {
                                    flex: "1",
                                    cursor: "pointer",
                                },
                                onclick: () => {
                                    addressRadio.checked = true;
                                    addressRadio.dispatchEvent(new Event("change"));
                                },
                            },
                            label(
                                {
                                    style: {
                                        fontSize: "var(--font-size-sm)",
                                        fontWeight: "var(--font-weight-medium)",
                                        display: "block",
                                        cursor: "pointer",
                                    },
                                },
                                "🏠 住所で検索",
                            ),
                            div(
                                {
                                    style: {
                                        fontSize: "var(--font-size-xs)",
                                        color: "var(--neutral-600)",
                                        marginTop: "2px",
                                    },
                                },
                                "正確な住所がわかる場合",
                            ),
                            div(
                                {
                                    style: {
                                        fontSize: "var(--font-size-xs)",
                                        color: "var(--neutral-500)",
                                        marginTop: "2px",
                                        fontStyle: "italic",
                                    },
                                },
                                '例: "東京都千代田区丸の内1-9-1"',
                            ),
                        ),
                    ),
                ),
            ),
            // 住所/施設名入力
            div(
                {},
                label(
                    {
                        style: {
                            fontWeight: "var(--font-weight-medium)",
                            fontSize: "var(--font-size-sm)",
                            color: "var(--foreground-color)",
                        },
                    },
                    "住所または施設名 *",
                ),
                queryInput,
                hintText,
                errorContainer,
            ),
            // 検索半径スライダー
            div(
                {},
                div(
                    {
                        style: {
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "8px",
                        },
                    },
                    label(
                        {
                            style: {
                                fontWeight: "var(--font-weight-medium)",
                                fontSize: "var(--font-size-sm)",
                                color: "var(--foreground-color)",
                            },
                        },
                        "検索半径",
                    ),
                    radiusLabel,
                ),
                radiusSlider,
                div(
                    {
                        style: {
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: "var(--font-size-xs)",
                            color: "var(--neutral-500)",
                            marginTop: "4px",
                        },
                    },
                    div({}, "50m"),
                    div({}, "500m"),
                ),
            ),
            // 詳細設定
            advancedToggle,
            advancedContainer,
        );

        const closeDialog = (result: DialogResult) => {
            if (result === DialogResult.ok) {
                // Validate query
                if (!query.trim()) {
                    showInlineError("住所または施設名を入力してください");
                    return;
                }

                dialog.remove();

                // 検索タイプに応じてパラメータを自動設定
                const options: PlateauSearchOptions = {
                    query: query.trim(),
                    radius,
                    buildingLimit: 10, // 候補を複数表示（固定）
                    autoReproject: true, // 常にtrue（固定）
                    mergeBuildingParts,

                    // 検索タイプに応じて分岐
                    ...(searchType === "facility"
                        ? {
                              searchMode: "hybrid" as const,
                              nameFilter: query.trim(), // ✅ 施設名をnameFilterに使用
                          }
                        : {
                              searchMode: "distance" as const,
                              nameFilter: undefined, // ✅ 住所検索ではnameFilterなし
                          }),
                };

                callback?.(DialogResult.ok, options);
            } else {
                dialog.remove();
                callback?.(DialogResult.cancel);
            }
        };

        dialog.appendChild(
            div(
                { className: style.root },
                div({ className: style.title }, "住所からインポート"),
                div({ className: style.content }, content),
                div(
                    { className: style.buttons },
                    button({
                        textContent: "検索する",
                        onclick: () => closeDialog(DialogResult.ok),
                        style: {
                            backgroundColor: "var(--primary-color)",
                            color: "white",
                            border: "none",
                            padding: "8px 16px",
                            borderRadius: "var(--radius-sm)",
                            cursor: "pointer",
                            fontWeight: "var(--font-weight-medium)",
                        },
                    }),
                    button({
                        textContent: "キャンセル",
                        onclick: () => closeDialog(DialogResult.cancel),
                        style: {
                            backgroundColor: "var(--neutral-200)",
                            color: "var(--foreground-color)",
                            border: "none",
                            padding: "8px 16px",
                            borderRadius: "var(--radius-sm)",
                            cursor: "pointer",
                        },
                    }),
                ),
            ),
        );

        // Handle keyboard shortcuts
        const handleKeydown = (e: KeyboardEvent) => {
            // Stop event propagation to prevent background shortcuts from triggering
            e.stopPropagation();

            if (e.key === "Escape") {
                e.preventDefault();
                closeDialog(DialogResult.cancel);
            } else if (e.key === "Enter" && !e.isComposing && e.target === queryInput) {
                // Allow Enter to submit from the query input (but not during IME composition)
                e.preventDefault();
                closeDialog(DialogResult.ok);
            }
        };

        dialog.addEventListener("keydown", handleKeydown);

        // Prevent click events from propagating to background
        dialog.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        dialog.showModal();

        // Focus on the first input
        setTimeout(() => {
            queryInput.focus();
        }, 100);
    }
}
