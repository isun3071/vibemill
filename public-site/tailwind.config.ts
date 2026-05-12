import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        // Warm off-black/off-white instead of pure values — editorial register.
        ink: {
          DEFAULT: "#1a1815",
          muted: "#5a564f",
          faint: "#8a857c",
        },
        paper: {
          DEFAULT: "#faf8f3",
          subtle: "#f0ede5",
        },
        // Dark mode pair
        night: {
          DEFAULT: "#15140f",
          subtle: "#1f1d18",
        },
        moon: {
          DEFAULT: "#e8e4d8",
          muted: "#a8a39a",
          faint: "#6e695f",
        },
      },
    },
  },
  plugins: [],
};

export default config;
