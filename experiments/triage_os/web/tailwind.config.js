/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#07090c", panel: "#0d1117", panel2: "#11161d", line: "#1c232c", line2: "#262f3a",
        ink: "#d7dde4", mute: "#7d8794", dim: "#4f5966",
        amber: { DEFAULT: "#f5a524", dim: "#8a5d14" }, up: "#2fbf71", down: "#ef4d5a", info: "#4ea1ff", violet: "#a78bfa",
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "IBM Plex Mono", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      fontSize: { xxs: ["10px", "14px"] },
    },
  },
  plugins: [],
}
