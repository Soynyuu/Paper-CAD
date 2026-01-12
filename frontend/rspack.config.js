const rspack = require("@rspack/core");
const { defineConfig } = require("@rspack/cli");
const ForkTsCheckerWebpackPlugin = require("fork-ts-checker-webpack-plugin");
const fs = require("fs");
const path = require("path");
const packages = require("./package.json");

// Minimal .env loader (no external dependency)
function loadEnv() {
    const mode = process.env.NODE_ENV || "development";
    const envFiles = [`.env.${mode}`, ".env"]; // priority: mode-specific then default
    for (const file of envFiles) {
        const p = path.join(__dirname, file);
        if (!fs.existsSync(p)) continue;
        const content = fs.readFileSync(p, "utf8");
        for (const line of content.split(/\r?\n/)) {
            if (!line || line.trim().startsWith("#")) continue;
            const eq = line.indexOf("=");
            if (eq === -1) continue;
            const key = line.slice(0, eq).trim();
            const raw = line.slice(eq + 1);
            // remove surrounding quotes if present
            const value = raw.replace(/^['"]|['"]$/g, "").trim();
            if (!(key in process.env)) process.env[key] = value;
        }
    }
}

loadEnv();

// PLATEAU-Terrain (ion asset 3258112). Override with CESIUM_TERRAIN_ASSET_ID if needed.
const DEFAULT_TERRAIN_ASSET_ID = 3258112;
const DEFAULT_PICK_LOD = 2;
const parseNumber = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
};

const isDev = process.env.NODE_ENV === "development";
let ReactRefreshPlugin = null;
if (isDev) {
    try {
        const reactRefreshModule = require("@rspack/plugin-react-refresh");
        ReactRefreshPlugin =
            reactRefreshModule?.default || reactRefreshModule?.ReactRefreshPlugin || reactRefreshModule;
    } catch (error) {
        ReactRefreshPlugin = null;
    }
}

const enableReactRefresh = isDev && typeof ReactRefreshPlugin === "function";
if (isDev && !enableReactRefresh) {
    console.warn(
        "[rspack] React refresh disabled. Install @rspack/plugin-react-refresh and react-refresh to enable it.",
    );
}

const resiumEntry = path.resolve(__dirname, "node_modules/resium/src/index.ts");

const config = defineConfig({
    entry: {
        main: "./packages/chili-web/src/index.ts",
    },
    mode: process.env.NODE_ENV === "production" ? "production" : "development",
    bail: false, // Continue building despite errors
    devServer: {
        hot: true,
        devMiddleware: {
            writeToDisk: true, // Write CopyRspackPlugin output to disk for SVG-Edit assets
        },
    },
    experiments: {
        css: true,
    },
    module: {
        parser: {
            "css/auto": {
                namedExports: false,
            },
        },
        rules: [
            {
                test: /\.wasm$/,
                type: "asset",
            },
            {
                test: /\.cur$/,
                type: "asset",
            },
            {
                test: /\.jpg$/,
                type: "asset",
            },
            {
                test: /\.(j|t)sx?$/,
                loader: "builtin:swc-loader",
                options: {
                    jsc: {
                        parser: {
                            syntax: "typescript",
                            tsx: true,
                            decorators: true,
                        },
                        transform: {
                            react: {
                                runtime: "automatic",
                                development: isDev,
                                refresh: enableReactRefresh,
                            },
                        },
                        target: "esnext",
                    },
                },
            },
        ],
    },
    resolve: {
        extensions: [".ts", ".tsx", ".js", ".jsx"],
        alias: {
            // Use resium source to avoid bundling a React 19 JSX runtime.
            resium: resiumEntry,
            resium$: resiumEntry,
            "resium/dist/resium.js": resiumEntry,
            "resium/dist/resium.umd.cjs": resiumEntry,
            // Fix @zip.js/zip.js compatibility with Cesium KML modules
            "@zip.js/zip.js/lib/zip-no-worker.js": "@zip.js/zip.js/lib/zip.js",
        },
        fallback: {
            fs: false,
            perf_hooks: false,
            os: false,
            crypto: false,
            stream: false,
            path: false,
        },
    },
    plugins: [
        new ForkTsCheckerWebpackPlugin(),
        new rspack.CopyRspackPlugin({
            patterns: [
                {
                    from: "./public",
                    globOptions: {
                        ignore: ["**/**/index.html"],
                    },
                },
                {
                    from: "./node_modules/svgedit/dist/editor",
                    to: "assets/svgedit",
                    globOptions: {
                        ignore: ["**/*.html", "**/*.js", "**/*.map"],
                    },
                },
                {
                    from: "./node_modules/cesium/Build/Cesium/Workers",
                    to: "cesium/Workers",
                },
                {
                    from: "./node_modules/cesium/Build/Cesium/Assets",
                    to: "cesium/Assets",
                },
                {
                    from: "./node_modules/cesium/Build/Cesium/Widgets",
                    to: "cesium/Widgets",
                },
                {
                    from: "./node_modules/cesium/Build/Cesium/ThirdParty",
                    to: "cesium/ThirdParty",
                },
            ],
        }),
        new rspack.DefinePlugin({
            __APP_VERSION__: JSON.stringify(packages.version),
            __DOCUMENT_VERSION__: JSON.stringify(packages.documentVersion),
            __APP_CONFIG__: JSON.stringify({
                stepUnfoldApiUrl:
                    process.env.STEP_UNFOLD_API_URL || "https://backend-paper-cad.soynyuu.com/api",
                stepUnfoldWsUrl: process.env.STEP_UNFOLD_WS_URL || null,
                cesiumBaseUrl: process.env.CESIUM_BASE_URL || "/cesium/",
                cesiumIonToken: process.env.CESIUM_ION_TOKEN || "",
                cesiumTerrainAssetId: parseNumber(
                    process.env.CESIUM_TERRAIN_ASSET_ID,
                    DEFAULT_TERRAIN_ASSET_ID,
                ),
                cesiumTerrainIonToken: process.env.CESIUM_TERRAIN_ION_TOKEN || "",
                cesiumPickLod: parseNumber(process.env.CESIUM_PICK_LOD, DEFAULT_PICK_LOD),
                useReactCesiumPicker: process.env.USE_REACT_CESIUM_PICKER === "true",
            }),
        }),
        new rspack.HtmlRspackPlugin({
            template: "./public/index.html",
            inject: "body",
        }),
        ...(enableReactRefresh ? [new ReactRefreshPlugin()] : []),
    ],
    optimization: {
        minimizer: [
            new rspack.SwcJsMinimizerRspackPlugin({
                minimizerOptions: {
                    mangle: {
                        keep_classnames: true,
                        keep_fnames: true,
                    },
                },
            }),
            new rspack.LightningCssMinimizerRspackPlugin(),
        ],
    },
});

module.exports = config;
