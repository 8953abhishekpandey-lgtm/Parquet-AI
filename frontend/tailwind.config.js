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
          300: "#b8b5ab",
          400: "#9a9688",
          500: "#6e6a5f",
          600: "#55524a",
          700: "#3f3b33",
          800: "#2a2722",
          900: "#171512",
          950: "#0d0c0a",
        },
        signal: {
          teal: "#0f766e",
          gold: "#b7791f",
          coral: "#c2410c",
          ink: "#111827",
          cyan: "#06b6d4",
          purple: "#8b5cf6",
          emerald: "#10b981",
        },
        glass: {
          white: "rgba(255, 255, 255, 0.08)",
          border: "rgba(255, 255, 255, 0.12)",
          hover: "rgba(255, 255, 255, 0.15)",
        },
      },
      boxShadow: {
        panel: "0 16px 42px rgba(0, 0, 0, 0.25)",
        "panel-hover": "0 20px 50px rgba(0, 0, 0, 0.35)",
        glow: "0 0 20px rgba(6, 182, 212, 0.15)",
        "glow-teal": "0 0 30px rgba(15, 118, 110, 0.2)",
        "glow-purple": "0 0 30px rgba(139, 92, 246, 0.15)",
        "inner-glow": "inset 0 1px 0 rgba(255, 255, 255, 0.06)",
      },
      backdropBlur: {
        xs: "2px",
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-out forwards",
        "slide-up": "slideUp 0.5s ease-out forwards",
        "slide-down": "slideDown 0.3s ease-out forwards",
        shimmer: "shimmer 2s infinite",
        "pulse-glow": "pulseGlow 2s ease-in-out infinite",
        "gradient-x": "gradientX 6s ease infinite",
        float: "float 3s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideDown: {
          "0%": { opacity: "0", transform: "translateY(-8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 15px rgba(6, 182, 212, 0.1)" },
          "50%": { boxShadow: "0 0 25px rgba(6, 182, 212, 0.25)" },
        },
        gradientX: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-4px)" },
        },
      },
    },
  },
  plugins: [],
};
