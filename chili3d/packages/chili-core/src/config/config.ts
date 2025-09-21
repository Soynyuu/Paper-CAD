// Centralized app config injected at build-time via Rspack DefinePlugin.
// See `rspack.config.js` where `__APP_CONFIG__` is defined.
declare const __APP_CONFIG__: {
    stepUnfoldApiUrl: string;
    stepUnfoldWsUrl?: string | null;
};

export const config = {
    stepUnfoldApiUrl: __APP_CONFIG__.stepUnfoldApiUrl,
    stepUnfoldWsUrl: __APP_CONFIG__.stepUnfoldWsUrl ?? undefined,
};
