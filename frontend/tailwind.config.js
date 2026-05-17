/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#1A1C1E",
        accent: "#B8422E",
        background: "#F7F5F2",
        surface: "#FCF8F8",
        secondary: "#A93724",
        "surface-container-lowest": "#FFFFFF",
        "surface-container-low": "#F6F3F2",
        "surface-container": "#F1EDED",
        "surface-container-high": "#EBE7E7",
        "surface-container-highest": "#E5E2E1",
        "border-subtle": "#E2E0DD",
        "text-muted": "#60646C",
      },
      borderRadius: {
        md: "8px",
        lg: "16px",
        xl: "24px",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      spacing: {
        "space-xs": "4px",
        "space-sm": "8px",
        "space-md": "16px",
        "space-lg": "24px",
        "space-xl": "32px",
        "sidebar-width": "260px",
        "header-height": "64px",
      },
      boxShadow: {
        terminal: "0 22px 70px rgba(26, 28, 30, 0.14)",
      },
    },
  },
  plugins: [],
};