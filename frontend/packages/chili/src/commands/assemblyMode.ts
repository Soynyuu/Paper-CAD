// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { AsyncController, CancelableCommand, command, I18n, INode, PubSub, ShapeNode } from "chili-core";
import { SelectNodeWithListStep } from "../step";

@command({
    key: "file.assemblyMode",
    icon: "icon-cube", // TODO: Add assembly-specific icon
})
export class AssemblyMode extends CancelableCommand {
    protected async executeAsync() {
        const nodes = await this.selectNodesAsync();
        if (!nodes || nodes.length === 0) {
            PubSub.default.pub("showToast", "toast.select.noSelected");
            return;
        }

        PubSub.default.pub(
            "showPermanent",
            async () => {
                try {
                    console.log("Assembly mode: Selected nodes:", nodes);

                    // 選択されたノードから3D形状データを取得
                    const shapeNode = nodes[0] as ShapeNode;
                    if (!shapeNode.shape) {
                        PubSub.default.pub("showToast", "toast.select.noSelected");
                        return;
                    }

                    // 3D形状をSTEPファイル形式でエクスポート（展開図生成のため）
                    const stepData = await this.application.dataExchange.export(".step", nodes);
                    if (!stepData) {
                        PubSub.default.pub("showToast", "toast.fail");
                        return;
                    }

                    // AssemblyPanelに切り替え
                    PubSub.default.pub("assemblyMode.showPanel", {
                        nodes: nodes,
                        stepData: Array.isArray(stepData) ? stepData[0] : stepData,
                    });

                    PubSub.default.pub("showToast", "toast.assemblyMode.started");
                } catch (error) {
                    console.error("Assembly mode error:", error);
                    PubSub.default.pub("showToast", "toast.assemblyMode.error");
                }
            },
            "toast.excuting{0}",
            I18n.translate("command.file.assemblyMode"),
        );
    }

    private async selectNodesAsync() {
        this.controller = new AsyncController();
        const step = new SelectNodeWithListStep("prompt.select.models", {
            multiple: false,
            keepSelection: true,
            allowListSelection: true,
            filter: {
                allow: (node: INode) => {
                    // ShapeNodeのみを選択可能にする
                    return (
                        node instanceof ShapeNode ||
                        (node as any).shape !== undefined ||
                        node.name?.toLowerCase().includes("pyramid") ||
                        node.name?.toLowerCase().includes("box") ||
                        node.name?.toLowerCase().includes("cylinder") ||
                        node.name?.toLowerCase().includes("untitled")
                    );
                },
            },
        });
        const data = await step.execute(this.application.activeView?.document!, this.controller);
        if (!data?.nodes) {
            PubSub.default.pub("showToast", "prompt.select.noModelSelected");
            return undefined;
        }
        return data.nodes;
    }
}
