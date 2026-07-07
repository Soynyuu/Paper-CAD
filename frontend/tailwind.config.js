const animate = require("tailwindcss-animate");

/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    corePlugins: {
        preflight: false,
    },
    content: ["./public/index.html", "./packages/**/*.{ts,tsx,js,jsx}"],
    theme: {
        extend: {
            fontFamily: {
                sans: "var(--font-family-sans)",
                mono: "var(--font-family-mono)",
            },
            colors: {
                border: "var(--border-color)",
                input: "var(--border-color)",
                ring: "var(--primary-color)",
                background: "var(--panel-background-color)",
                foreground: "var(--foreground-color)",
                primary: {
                    DEFAULT: "var(--primary-color)",
                    foreground: "var(--neutral-0)",
                },
                secondary: {
                    DEFAULT: "var(--background-color)",
                    foreground: "var(--foreground-color)",
                },
                destructive: {
                    DEFAULT: "var(--danger-color, #e74c3c)",
                    foreground: "var(--neutral-0)",
                },
                muted: {
                    DEFAULT: "var(--background-color)",
                    foreground: "var(--neutral-500)",
                },
                accent: {
                    DEFAULT: "var(--hover-background-color)",
                    foreground: "var(--foreground-color)",
                },
                popover: {
                    DEFAULT: "var(--panel-background-color)",
                    foreground: "var(--foreground-color)",
                },
                card: {
                    DEFAULT: "var(--panel-background-color)",
                    foreground: "var(--foreground-color)",
                },
            },
            borderRadius: {
                lg: "var(--radius-sm, 4px)",
                md: "var(--radius-sm, 4px)",
                sm: "var(--radius-xs, 2px)",
            },
        },
    },
    plugins: [animate],
};
