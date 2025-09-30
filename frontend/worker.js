import { getAssetFromKV, mapRequestToAsset } from "@cloudflare/kv-asset-handler";

/**
 * The DEBUG flag will do two things that help during development:
 * 1. we will skip caching on the edge, which makes it easier to
 *    debug.
 * 2. we will return an error message on exception in your Response rather
 *    than the default 404.html page.
 */
const DEBUG = false;

addEventListener("fetch", (event) => {
    event.respondWith(handleEvent(event));
});

async function handleEvent(event) {
    let options = {};
    try {
        if (DEBUG) {
            // customize caching
            options.cacheControl = {
                bypassCache: true,
            };
        }

        const page = await getAssetFromKV(event, options);

        // allow headers to be altered
        const response = new Response(page.body, page);

        // Set CORS headers
        response.headers.set("Access-Control-Allow-Origin", "*");
        response.headers.set("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS");
        response.headers.set("Access-Control-Allow-Headers", "*");

        // Set appropriate headers for different file types
        const url = new URL(event.request.url);
        const extension = url.pathname.split(".").pop();

        if (extension === "wasm") {
            response.headers.set("Content-Type", "application/wasm");
        } else if (extension === "js" || extension === "mjs") {
            response.headers.set("Content-Type", "application/javascript");
        } else if (extension === "css") {
            response.headers.set("Content-Type", "text/css");
        } else if (extension === "html" || url.pathname === "/" || !extension) {
            response.headers.set("Content-Type", "text/html");
        } else if (extension === "json") {
            response.headers.set("Content-Type", "application/json");
        } else if (["png", "jpg", "jpeg", "gif", "svg", "ico"].includes(extension)) {
            // Image types are usually set correctly by KV
        }

        // Set cache headers for production
        if (!DEBUG) {
            if (["js", "css", "wasm"].includes(extension)) {
                response.headers.set("Cache-Control", "public, max-age=31536000, immutable");
            } else if (["png", "jpg", "jpeg", "gif", "svg", "ico"].includes(extension)) {
                response.headers.set("Cache-Control", "public, max-age=86400");
            } else {
                response.headers.set("Cache-Control", "public, max-age=3600");
            }
        }

        return response;
    } catch (e) {
        // if an error is thrown try to serve the asset at 404.html
        if (!DEBUG) {
            try {
                let notFoundResponse = await getAssetFromKV(event, {
                    mapRequestToAsset: (req) => new Request(`${new URL(req.url).origin}/index.html`, req),
                });

                return new Response(notFoundResponse.body, {
                    ...notFoundResponse,
                    status: 404,
                });
            } catch (e) {}
        }

        return new Response(e.message || e.toString(), { status: 500 });
    }
}

/**
 * Here's one example of how to modify a request to
 * remove a specific prefix, in this case `/docs` from
 * the url. This can be useful if you are deploying to a
 * route on a zone, or if you only want your static content
 * to exist at a specific path.
 */
function handlePrefix(prefix) {
    return (request) => {
        // compute the default (e.g. / -> index.html)
        let defaultAssetKey = mapRequestToAsset(request);
        let url = new URL(defaultAssetKey.url);

        // strip the prefix from the path for lookup
        url.pathname = url.pathname.replace(prefix, "/");

        // inherit all other props from the default request
        return new Request(url.toString(), defaultAssetKey);
    };
}
