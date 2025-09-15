// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { div } from "chili-controls";
import {
    AsyncController,
    Button,
    CommandKeys,
    I18nKeys,
    IApplication,
    IDocument,
    Material,
    PubSub,
    RibbonTab,
} from "chili-core";
import { ResizablePanels } from "./components";
import style from "./editor.module.css";
import { OKCancel } from "./okCancel";
import { ProjectView } from "./project";
import { PropertyView } from "./property";
import { MaterialDataContent, MaterialEditor } from "./property/material";
import { Ribbon, RibbonDataContent } from "./ribbon";
import { RibbonTabData } from "./ribbon/ribbonData";
import { Statusbar } from "./statusbar";
import { StepUnfoldPanel, StepUnfoldTestUtils } from "./stepUnfold";
import { LayoutViewport } from "./viewport";

let quickCommands: CommandKeys[] = ["doc.save", "doc.saveToFile", "edit.undo", "edit.redo"];

export class Editor extends HTMLElement {
    readonly ribbonContent: RibbonDataContent;
    private readonly _selectionController: OKCancel;
    private readonly _viewportContainer: HTMLDivElement;
    private readonly _stepUnfoldPanel: StepUnfoldPanel;
    private readonly _app: IApplication;
    private readonly _resizablePanels: ResizablePanels;

    constructor(app: IApplication, tabs: RibbonTab[]) {
        super();
        this._app = app;
        this.ribbonContent = new RibbonDataContent(app, quickCommands, tabs.map(RibbonTabData.fromProfile));
        const viewport = new LayoutViewport(app);
        viewport.classList.add(style.viewport);
        this._selectionController = new OKCancel();
        this._viewportContainer = div(
            { className: style.viewportContainer },
            this._selectionController,
            viewport,
        );
        this._stepUnfoldPanel = new StepUnfoldPanel(app);
        this._stepUnfoldPanel.classList.add(style.stepUnfoldPanel);
        console.log("Editor: Created stepUnfoldPanel:", this._stepUnfoldPanel);

        // リサイズ可能なパネルを作成
        this._resizablePanels = new ResizablePanels({
            leftPanel: this._viewportContainer,
            rightPanel: this._stepUnfoldPanel,
            initialLeftWidth: window.innerWidth * 0.7, // 画面幅の70%を初期値に
            minLeftWidth: 400,
            maxLeftWidth: window.innerWidth - 400, // 右パネルが最低400px確保できるように
            className: style.resizableContent,
            storageKey: "editor-main-panels",
        });

        this.clearSelectionControl();
        this.render();
        document.body.appendChild(this);

        // デバッグ用: テストユーティリティを初期化
        StepUnfoldTestUtils.testBackendConnection();
    }

    private render() {
        this.append(
            div(
                { className: style.root },
                new Ribbon(this.ribbonContent),
                div(
                    { className: style.content },
                    div(
                        { className: style.sidebar },
                        new ProjectView({ className: style.sidebarItem }),
                        new PropertyView({ className: style.sidebarItem }),
                    ),
                    this._resizablePanels,
                ),
                new Statusbar(style.statusbar),
            ),
        );
    }

    connectedCallback(): void {
        PubSub.default.sub("showSelectionControl", this.showSelectionControl);
        PubSub.default.sub("editMaterial", this._handleMaterialEdit);
        PubSub.default.sub("clearSelectionControl", this.clearSelectionControl);

        // ウィンドウリサイズ時にmax幅を更新
        window.addEventListener("resize", this._handleWindowResize);
    }

    disconnectedCallback(): void {
        PubSub.default.remove("showSelectionControl", this.showSelectionControl);
        PubSub.default.remove("editMaterial", this._handleMaterialEdit);
        PubSub.default.remove("clearSelectionControl", this.clearSelectionControl);

        window.removeEventListener("resize", this._handleWindowResize);
    }

    private readonly _handleWindowResize = () => {
        if (this._resizablePanels) {
            this._resizablePanels.setMinMaxWidth(400, window.innerWidth - 400);
        }
    };

    private readonly showSelectionControl = (controller: AsyncController) => {
        this._selectionController.setControl(controller);
        this._selectionController.style.visibility = "visible";
        this._selectionController.style.zIndex = "1000";
    };

    private readonly clearSelectionControl = () => {
        this._selectionController.setControl(undefined);
        this._selectionController.style.visibility = "hidden";
    };

    private readonly _handleMaterialEdit = (
        document: IDocument,
        editingMaterial: Material,
        callback: (material: Material) => void,
    ) => {
        let context = new MaterialDataContent(document, callback, editingMaterial);
        this._viewportContainer.append(new MaterialEditor(context));
    };

    registerRibbonCommand(tabName: I18nKeys, groupName: I18nKeys, command: CommandKeys | Button) {
        const tab = this.ribbonContent.ribbonTabs.find((p) => p.tabName === tabName);
        const group = tab?.groups.find((p) => p.groupName === groupName);
        group?.items.push(command);
    }
}

customElements.define("chili-editor", Editor);
