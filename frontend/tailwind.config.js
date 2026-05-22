/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        sidebar: "#0f172a",
      },
      keyframes: {
        "typing-dot": {
          "0%, 80%, 100%": { opacity: "0.2", transform: "scale(0.75)" },
          "40%": { opacity: "1", transform: "scale(1)" },
        },
        "msg-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
      animation: {
        "typing-dot-1": "typing-dot 1.2s ease-in-out infinite",
        "typing-dot-2": "typing-dot 1.2s ease-in-out 0.2s infinite",
        "typing-dot-3": "typing-dot 1.2s ease-in-out 0.4s infinite",
        "msg-in": "msg-in 0.18s ease-out forwards",
        "fade-in": "fade-in 0.2s ease-out forwards",
      },
    },
  },
  plugins: [],
};
