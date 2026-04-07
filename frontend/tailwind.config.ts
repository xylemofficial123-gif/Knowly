import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#ffffff",
        foreground: "#0a0a0f",
        accent: {
          DEFAULT: "#16a34a", // Leaf green — matches Xylem brand
          light: "#22c55e",
          dark: "#15803d",
          soft: "#f0fdf4",
        },
        sidebar: {
          bg: "#ffffff",
          hover: "#f0fdf4",
          active: "#dcfce7",
          text: "#64748b",
        },
        border: {
          DEFAULT: "#f1f5f9",
          strong: "#e2e8f0",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
    },
  },
  plugins: [],
};
export default config;
