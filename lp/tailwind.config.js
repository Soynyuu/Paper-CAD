/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          orange: '#F05A28',
          black: '#181715',
          gray: '#F7F4EE',
        }
      },
      fontFamily: {
        sans: ['"Gen Interface JP"', '"Noto Sans JP"', 'sans-serif'],
        mono: ['"Roboto Mono"', 'monospace'],
      },
      letterSpacing: {
        tight: '-0.02em',
        normal: '0.05em', // Increased from 0.02em
        wide: '0.1em',   // Increased from 0.05em
        widest: '0.2em',
      }
    },
  },
  plugins: [],
}
