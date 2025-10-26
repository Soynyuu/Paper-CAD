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

const config = defineConfig({
    entry: {
        main: "./packages/chili-web/src/index.ts",
    },
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
                test: /\.(j|t)s$/,
                loader: "builtin:swc-loader",
                options: {
                    jsc: {
                        parser: {
                            syntax: "typescript",
                            decorators: true,
                        },
                        target: "esnext",
                    },
                },
            },
        ],
    },
    resolve: {
        extensions: [".ts", ".js"],
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
            ],
        }),
        new rspack.DefinePlugin({
            __APP_VERSION__: JSON.stringify(packages.version),
            __DOCUMENT_VERSION__: JSON.stringify(packages.documentVersion),
            __APP_CONFIG__: JSON.stringify({
                stepUnfoldApiUrl:
                    process.env.STEP_UNFOLD_API_URL || "https://backend-paper-cad.soynyuu.com/api",
                stepUnfoldWsUrl: process.env.STEP_UNFOLD_WS_URL || null,
            }),
        }),
        new rspack.HtmlRspackPlugin({
            template: "./public/index.html",
            inject: "body",
        }),
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
