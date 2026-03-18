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
          DEFAULT: "#5a4efb", // Bright Navy/Indigo from image
          light: "#7c72ff",
          dark: "#4a3eeb",
          soft: "#f0efff",
        },
        sidebar: {
          bg: "#ffffff",
          hover: "#f8f9fc",
          active: "#eff2ff",
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
