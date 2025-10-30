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
    private _sidebarCollapsed: boolean = false;
    private readonly _sidebar: HTMLDivElement;
    private readonly _toggleButton: HTMLButtonElement;

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

        // サイドバーを作成
        this._sidebar = div(
            { className: style.sidebar },
            new ProjectView({ className: style.sidebarItem }),
            new PropertyView({ className: style.sidebarItem }),
        );

        // 折りたたみボタンを作成
        this._toggleButton = document.createElement("button");
        this._toggleButton.className = style.sidebarToggle;
        this._toggleButton.textContent = "◀";
        this._toggleButton.onclick = () => this.toggleSidebar();

        // LocalStorageから状態を復元
        const savedState = localStorage.getItem("editor-sidebar-collapsed");
        if (savedState === "true") {
            this._sidebarCollapsed = true;
            this._sidebar.classList.add(style.collapsed);
            this._toggleButton.textContent = "▶";
        }

        // リサイズ可能なパネルを作成
        // サイドバーの幅を考慮して、残りの領域を50:50に分割
        const sidebarWidth = this._sidebarCollapsed ? 40 : 280;
        const availableWidth = window.innerWidth - sidebarWidth;
        this._resizablePanels = new ResizablePanels({
            leftPanel: this._viewportContainer,
            rightPanel: this._stepUnfoldPanel,
            initialLeftWidth: availableWidth * 0.5, // 利用可能な幅の50%を初期値に（半々の比率）
            minLeftWidth: 400,
            maxLeftWidth: availableWidth - 400, // 右パネルが最低400px確保できるように
            className: style.resizableContent,
            storageKey: "editor-main-panels-v2", // v2に変更して新しい初期値を適用
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
                div({ className: style.content }, this._sidebar, this._toggleButton, this._resizablePanels),
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
            const sidebarAdjust = this._sidebarCollapsed ? 40 : 400;
            this._resizablePanels.setMinMaxWidth(400, window.innerWidth - sidebarAdjust);
        }
    };

    private toggleSidebar() {
        this._sidebarCollapsed = !this._sidebarCollapsed;

        if (this._sidebarCollapsed) {
            this._sidebar.classList.add(style.collapsed);
            this._toggleButton.textContent = "▶";
        } else {
            this._sidebar.classList.remove(style.collapsed);
            this._toggleButton.textContent = "◀";
        }

        // 状態を保存
        localStorage.setItem("editor-sidebar-collapsed", this._sidebarCollapsed.toString());

        // リサイズパネルの幅を調整
        if (this._resizablePanels) {
            const sidebarAdjust = this._sidebarCollapsed ? 40 : 400;
            this._resizablePanels.setMinMaxWidth(400, window.innerWidth - sidebarAdjust);
        }
    }

    private readonly showSelectionControl = (controller: AsyncController) => {
        const document = this._app.activeView?.document;
        this._selectionController.setControl(controller, document);
        this._selectionController.style.visibility = "visible";
        this._selectionController.style.zIndex = "1000";
    };

    private readonly clearSelectionControl = () => {
        this._selectionController.setControl(undefined, undefined);
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
