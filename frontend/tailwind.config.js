/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        graphite: {
          50: "#f7f7f5",
          100: "#ecebe7",
          200: "#d8d6ce",
          500: "#6e6a5f",
          700: "#3f3b33",
          900: "#171512",
        },
        signal: {
          teal: "#0f766e",
          gold: "#b7791f",
          coral: "#c2410c",
          ink: "#111827",
        },
      },
      boxShadow: {
        panel: "0 16px 42px rgba(23, 21, 18, 0.08)",
      },
    },
  },
  plugins: [],
};

