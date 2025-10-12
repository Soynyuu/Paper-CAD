// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { RibbonTab } from "chili-core";

export const DefaultRibbon: RibbonTab[] = [
    {
        tabName: "ribbon.tab.startup",
        groups: [
            {
                groupName: "ribbon.group.draw",
                items: [
                    "create.line",
                    "create.arc",
                    "create.rect",
                    "create.circle",
                    ["create.ellipse", "create.bezier", "create.polygon"],
                    ["create.box", "create.pyramid", "create.cylinder"],
                    ["create.cone", "create.sphere", "create.thickSolid"],
                ],
            },
            {
                groupName: "ribbon.group.importExport",
                items: [
                    "file.import",
                    ["file.importCityGML", "file.importCityGMLByAddress"],
                    "file.export",
                    "file.stepUnfold",
                    "file.assemblyMode",
                ],
            },
            {
                groupName: "ribbon.group.measure",
                items: [["measure.length", "measure.angle", "measure.select"]],
            },
        ],
    },
    {
        tabName: "ribbon.tab.modify",
        groups: [
            {
                groupName: "ribbon.group.transform",
                items: ["modify.move", "modify.rotate", "modify.mirror"],
            },
            {
                groupName: "ribbon.group.edit",
                items: [
                    ["modify.split", "modify.break", "modify.trim"],
                    ["modify.fillet", "modify.chamfer", "modify.explode"],
                    ["modify.deleteNode", "modify.removeShapes", "modify.removeFeature"],
                    "modify.applyTexture",
                ],
            },
            {
                groupName: "ribbon.group.brush",
                items: [["modify.brushAdd", "modify.brushRemove", "modify.brushClear"]],
            },
        ],
    },
    {
        tabName: "ribbon.tab.converter",
        groups: [
            {
                groupName: "ribbon.group.converter",
                items: [
                    "create.extrude",
                    "convert.sweep",
                    "convert.revol",
                    "convert.toWire",
                    "convert.curveProjection",
                    ["convert.toFace", "convert.toShell", "convert.toSolid"],
                ],
            },
            {
                groupName: "ribbon.group.boolean",
                items: [["boolean.common", "boolean.cut", "boolean.join"]],
            },
        ],
    },
    {
        tabName: "ribbon.tab.tools",
        groups: [
            {
                groupName: "ribbon.group.workingPlane",
                items: [
                    "workingPlane.toggleDynamic",
                    ["workingPlane.set", "workingPlane.alignToPlane", "workingPlane.fromSection"],
                ],
            },
            {
                groupName: "ribbon.group.tools",
                items: ["create.group", ["create.section", "create.offset", "create.copyShape"]],
            },
            {
                groupName: "ribbon.group.act",
                items: ["act.alignCamera"],
            },
            {
                groupName: "ribbon.group.other",
                items: ["test.performace", "settings.units", "settings.keymap"],
            },
        ],
    },
];
