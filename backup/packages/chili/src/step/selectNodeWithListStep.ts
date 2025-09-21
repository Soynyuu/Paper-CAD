// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { AsyncController, I18nKeys, IDocument, INodeFilter, PubSub } from "chili-core";
import { SnapResult } from "../snap";
import { IStep } from "./step";

export interface SelectNodeWithListOptions {
    multiple?: boolean;
    filter?: INodeFilter;
    keepSelection?: boolean;
    allowListSelection?: boolean;
}

export class SelectNodeWithListStep implements IStep {
    constructor(
        readonly prompt: I18nKeys,
        readonly options?: SelectNodeWithListOptions,
    ) {}

    async execute(document: IDocument, controller: AsyncController): Promise<SnapResult | undefined> {
        const { nodeFilter } = document.selection;
        document.selection.nodeFilter = this.options?.filter;
        if (!this.options?.keepSelection) {
            document.selection.clearSelection();
            document.visual.highlighter.clear();
        }

        try {
            // リスト選択が有効な場合、selection controllerを表示
            if (this.options?.allowListSelection) {
                PubSub.default.pub("showSelectionControl", controller);
            }

            // 通常の選択ロジックを使用（アイテムリストからも選択可能）
            const nodes = await document.selection.pickNode(
                this.prompt,
                controller,
                this.options?.multiple === true,
            );

            if (nodes.length === 0) return undefined;

            return {
                view: document.application.activeView!,
                shapes: [],
                nodes,
            };
        } finally {
            document.selection.nodeFilter = nodeFilter;
            if (this.options?.allowListSelection) {
                PubSub.default.pub("clearSelectionControl");
            }
        }
    }
}
