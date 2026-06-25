import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        risk: {
          high: "#ef4444",
          medium: "#f97316",
          low: "#22c55e",
        },
      },
    },
  },
  plugins: [],
};

export default config;
