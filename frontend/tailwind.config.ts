import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        severity: {
          high: {
            bg: "rgb(254 242 242)", // red-50
            border: "rgb(254 202 202)", // red-200
            text: "rgb(185 28 28)", // red-700
            darkBg: "rgba(69, 10, 10, 0.4)",
            darkBorder: "rgb(127 29 29)",
            darkText: "rgb(248 113 113)",
          },
          medium: {
            bg: "rgb(255 251 235)", // amber-50
            border: "rgb(253 230 138)", // amber-200
            text: "rgb(180 83 9)", // amber-700
            darkBg: "rgba(69, 26, 3, 0.4)",
            darkBorder: "rgb(120 53 15)",
            darkText: "rgb(251 191 36)",
          },
          low: {
            bg: "rgb(241 245 249)", // slate-100
            border: "rgb(226 232 240)", // slate-200
            text: "rgb(71 85 105)", // slate-600
            darkBg: "rgba(30, 41, 59, 0.5)",
            darkBorder: "rgb(51 65 85)",
            darkText: "rgb(148 163 184)",
          },
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
