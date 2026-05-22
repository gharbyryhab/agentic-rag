/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#2563eb", hover: "#1d4ed8" },
        surface: "#f8fafc",
      },
    },
  },
  plugins: [],
};
