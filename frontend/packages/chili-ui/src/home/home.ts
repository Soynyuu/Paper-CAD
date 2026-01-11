// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { a, button, collection, div, img, label, span, svg } from "chili-controls";
import {
    Constants,
    I18n,
    I18nKeys,
    IApplication,
    Localize,
    ObservableCollection,
    PubSub,
    RecentDocumentDTO,
} from "chili-core";

import style from "./home.module.css";
import { LanguageSelector } from "./languageSelector";
import { Navigation3DSelector } from "./navigation3DSelector";

interface ApplicationCommand {
    display: I18nKeys;
    icon?: string;
    onclick: () => void;
}

const applicationCommands = new ObservableCollection<ApplicationCommand>(
    {
        display: "command.doc.new",
        icon: "icon-file-plus",
        onclick: () => PubSub.default.pub("executeCommand", "doc.new"),
    },
    {
        display: "command.doc.open",
        icon: "icon-folder-open",
        onclick: () => PubSub.default.pub("executeCommand", "doc.open"),
    },
);

export class Home extends HTMLElement {
    constructor(readonly app: IApplication) {
        super();
        this.className = style.root;
    }

    private hasOpen(documentId: string) {
        for (const document of this.app.documents) {
            if (document.id === documentId) return true;
        }
        return false;
    }

    private async getDocuments() {
        return new ObservableCollection(
            ...(await this.app.storage.page(Constants.DBName, Constants.RecentTable, 0)),
        );
    }

    async render() {
        const documents = await this.getDocuments();
        this.append(this.leftSection(), this.rightSection(documents));
        document.body.appendChild(this);
    }

    private leftSection() {
        return div(
            { className: style.left },
            div(
                { className: style.top },
                this.logoSection(),
                this.applicationCommands(),
                this.currentDocument(),
            ),

            this.settings(),
        );
    }

    private logoSection() {
        return div(
            { className: style.logo },
            span({ textContent: "PAPER-CAD" }),
            span({ className: style.version, textContent: __APP_VERSION__ }),
        );
    }

    private applicationCommands() {
        return collection({
            className: style.buttons,
            sources: applicationCommands,
            template: (item) =>
                button(
                    {
                        className: style.button,
                        onclick: item.onclick,
                    },
                    div(
                        { style: { display: "flex", alignItems: "center", gap: "12px" } },
                        item.icon
                            ? svg({
                                  icon: item.icon,
                                  style: { width: "18px", height: "18px", opacity: "0.7" },
                              })
                            : "",
                        span({ textContent: new Localize(item.display) }),
                    ),
                ),
        });
    }

    private currentDocument() {
        return this.app.activeView?.document
            ? button({
                  className: `${style.button} ${style.back}`,
                  textContent: new Localize("common.back"),
                  onclick: () => {
                      PubSub.default.pub("displayHome", false);
                  },
              })
            : "";
    }

    private settings() {
        return div(
            { className: style.settingsPanel },
            div(
                { className: style.settingItem },
                span({
                    className: style.settingLabel,
                    textContent: new Localize("common.language"),
                }),
                div({ className: style.settingControl }, LanguageSelector({})),
            ),
            div(
                { className: style.settingItem },
                span({
                    className: style.settingLabel,
                    textContent: new Localize("common.3DNavigation"),
                }),
                div({ className: style.settingControl }, Navigation3DSelector({})),
            ),
        );
    }

    private rightSection(documents: ObservableCollection<RecentDocumentDTO>) {
        return div(
            { className: style.right },
            label({ className: style.welcome, textContent: new Localize("home.welcome") }),
            this.heroSection(),
            div({ className: style.recent, textContent: new Localize("home.recent") }),
            this.documentCollection(documents),
        );
    }

    private heroSection() {
        return div(
            { className: style.heroSection },
            // Card 1: New
            div(
                {
                    className: style.heroCard,
                    onclick: () => PubSub.default.pub("executeCommand", "doc.new"),
                },
                svg({ icon: "icon-file-plus", className: style.heroIcon }),
                div({ className: style.heroTitle, textContent: new Localize("command.doc.new") }),
                div({
                    className: style.heroDescription,
                    textContent:
                        I18n.translate("common.language") === "日本語"
                            ? "何もない空間から自由に作成"
                            : "Start from scratch",
                }),
            ),
            // Card 2: Map (Primary)
            div(
                {
                    className: style.heroCard,
                    style: { borderColor: "var(--primary-color)", backgroundColor: "var(--neutral-0)" },
                    onclick: () => {
                        console.log("[Home] PLATEAU button clicked");
                        PubSub.default.pub("executeCommand", "file.importPlateauBuilding");
                    },
                },
                svg({ icon: "icon-position", className: style.heroIcon }),
                div({
                    className: style.heroTitle,
                    textContent: new Localize("command.file.importPlateauBuilding"),
                }),
                div({
                    className: style.heroDescription,
                    textContent:
                        I18n.translate("common.language") === "日本語"
                            ? "検索から3D地図で建物を選んで作成"
                            : "Search and pick building from 3D Map",
                }),
            ),
        );
    }

    private documentCollection(documents: ObservableCollection<RecentDocumentDTO>) {
        return collection({
            className: style.documents,
            sources: documents,
            template: (item) => this.recentDocument(item, documents),
        });
    }

    private recentDocument(item: RecentDocumentDTO, documents: ObservableCollection<RecentDocumentDTO>) {
        return div(
            {
                className: style.document,
                onclick: () => this.handleDocumentClick(item),
            },
            img({ className: style.img, src: item.image }),
            this.documentDescription(item),
            this.deleteIcon(item, documents),
        );
    }

    private documentDescription(item: RecentDocumentDTO) {
        return div(
            { className: style.description },
            span({ className: style.title, textContent: item.name }),
            span({
                className: style.date,
                textContent: new Date(item.date).toLocaleDateString(),
            }),
        );
    }

    private deleteIcon(item: RecentDocumentDTO, documents: ObservableCollection<RecentDocumentDTO>) {
        return svg({
            className: style.delete,
            icon: "icon-times",
            onclick: async (e) => {
                e.stopPropagation();
                if (window.confirm(I18n.translate("prompt.deleteDocument{0}", item.name))) {
                    await Promise.all([
                        this.app.storage.delete(Constants.DBName, Constants.DocumentTable, item.id),
                        this.app.storage.delete(Constants.DBName, Constants.RecentTable, item.id),
                    ]);
                    documents.remove(item);
                }
            },
        });
    }

    private handleDocumentClick(item: RecentDocumentDTO) {
        if (this.hasOpen(item.id)) {
            PubSub.default.pub("displayHome", false);
        } else {
            PubSub.default.pub(
                "showPermanent",
                async () => {
                    let document = await this.app.openDocument(item.id);
                    document?.application.activeView?.cameraController.fitContent();
                },
                "toast.excuting{0}",
                I18n.translate("command.doc.open"),
            );
        }
    }
}

customElements.define("chili-home", Home);
