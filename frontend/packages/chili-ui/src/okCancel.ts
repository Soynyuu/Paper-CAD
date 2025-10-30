// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { div, span, svg } from "chili-controls";
import { AsyncController, I18nKeys, Localize, IDocument, PubSub } from "chili-core";
import style from "./okCancel.module.css";

export class OKCancel extends HTMLElement {
    private control?: AsyncController;
    private document?: IDocument;
    private selectionCountDisplay?: HTMLSpanElement;

    constructor() {
        super();
        this.className = style.root;
        this.append(this.container());

        // Subscribe to selection changes
        PubSub.default.sub("selectionChanged", this._onSelectionChanged);
    }

    private container() {
        // Create selection count display element
        this.selectionCountDisplay = span({
            className: style.selectionCount,
            textContent: "",
        });

        return div(
            { className: style.container },
            span({ textContent: new Localize("ribbon.group.selection") }),
            this.selectionCountDisplay,
            div({ className: style.spacer }),
            this.buttons(),
        );
    }

    private buttons() {
        return div(
            { className: style.panel },
            this._createIcon("icon-confirm", "common.confirm", this._onConfirm),
            this._createIcon("icon-cancel", "common.cancel", this._onCancel),
        );
    }

    private _createIcon(icon: string, text: I18nKeys, onClick: () => void) {
        return div(
            {
                className: style.icon,
                onclick: onClick,
            },
            svg({ icon }),
            span({ textContent: new Localize(text) }),
        );
    }

    setControl(control: AsyncController | undefined, document?: IDocument) {
        this.control = control;
        this.document = document;

        // Update selection count immediately
        this._updateSelectionCount();
    }

    private readonly _onSelectionChanged = (doc: IDocument, selected: any[], unselected: any[]) => {
        // Only update if this is for the current document
        if (this.document === doc) {
            this._updateSelectionCount();
        }
    };

    private _updateSelectionCount() {
        if (!this.selectionCountDisplay || !this.document) {
            return;
        }

        const selectedNodes = this.document.selection.getSelectedNodes();
        const count = selectedNodes.length;

        if (count === 0) {
            this.selectionCountDisplay.textContent = "";
        } else if (count === 1) {
            this.selectionCountDisplay.textContent = " (1 item)";
        } else {
            this.selectionCountDisplay.textContent = ` (${count} items)`;
        }
    }

    private readonly _onConfirm = () => {
        this.control?.success();
    };

    private readonly _onCancel = () => {
        this.control?.cancel();
    };
}

customElements.define("ok-cancel", OKCancel);
