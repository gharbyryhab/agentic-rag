/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        // Design system: Stellar
        surface: {
          50:  "#f8f9ff",
          100: "#0d0e1e",
          200: "#12132a",
          300: "#1a1b35",
          400: "#22244a",
        },
        sidebar: "#08091a",
        // Accent
        brand: {
          DEFAULT: "#6366f1",
          light:   "#818cf8",
          dark:    "#4f46e5",
          glow:    "rgba(99,102,241,0.35)",
        },
      },
      backgroundImage: {
        "gradient-radial":  "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":   "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "glass-gradient":   "linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%)",
        "hero-gradient":    "radial-gradient(ellipse at top, #1e1b4b 0%, #080812 60%)",
        "card-gradient":    "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.04) 100%)",
        "active-gradient":  "linear-gradient(90deg, rgba(99,102,241,0.25) 0%, rgba(99,102,241,0.05) 100%)",
      },
      boxShadow: {
        "glow-sm":  "0 0 15px rgba(99,102,241,0.3)",
        "glow":     "0 0 30px rgba(99,102,241,0.4)",
        "glow-lg":  "0 0 60px rgba(99,102,241,0.35)",
        "glow-violet": "0 0 30px rgba(139,92,246,0.35)",
        "card":     "0 4px 24px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        "card-hover":"0 8px 40px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.4)",
        "inner-glow":"inset 0 1px 0 rgba(255,255,255,0.08)",
      },
      keyframes: {
        "typing-dot": {
          "0%, 80%, 100%": { opacity: "0.2", transform: "scale(0.75)" },
          "40%":            { opacity: "1",   transform: "scale(1)" },
        },
        "msg-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(20px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "toast-in": {
          from: { opacity: "0", transform: "translateX(110%)" },
          to:   { opacity: "1", transform: "translateX(0)" },
        },
        "toast-out": {
          from: { opacity: "1", transform: "translateX(0)" },
          to:   { opacity: "0", transform: "translateX(110%)" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%":      { transform: "translateY(-20px)" },
        },
        "float-slow": {
          "0%, 100%": { transform: "translateY(0px) scale(1)" },
          "50%":      { transform: "translateY(-30px) scale(1.05)" },
        },
        "shimmer": {
          "0%":   { backgroundPosition: "-500px 0" },
          "100%": { backgroundPosition: "500px 0" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 15px rgba(99,102,241,0.3)" },
          "50%":      { boxShadow: "0 0 35px rgba(99,102,241,0.6)" },
        },
        "orb": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "33%":      { transform: "translate(60px, -40px) scale(1.1)" },
          "66%":      { transform: "translate(-30px, 50px) scale(0.95)" },
        },
        "orb2": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "33%":      { transform: "translate(-50px, 60px) scale(1.08)" },
          "66%":      { transform: "translate(70px, -20px) scale(0.92)" },
        },
      },
      animation: {
        "typing-dot-1": "typing-dot 1.2s ease-in-out infinite",
        "typing-dot-2": "typing-dot 1.2s ease-in-out 0.2s infinite",
        "typing-dot-3": "typing-dot 1.2s ease-in-out 0.4s infinite",
        "msg-in":       "msg-in 0.22s ease-out forwards",
        "fade-in":      "fade-in 0.25s ease-out forwards",
        "slide-up":     "slide-up 0.35s ease-out forwards",
        "toast-in":     "toast-in 0.22s ease-out forwards",
        "toast-out":    "toast-out 0.22s ease-in forwards",
        "float":        "float 6s ease-in-out infinite",
        "float-slow":   "float-slow 8s ease-in-out infinite",
        "glow-pulse":   "glow-pulse 2s ease-in-out infinite",
        "orb":          "orb 12s ease-in-out infinite",
        "orb2":         "orb2 15s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
