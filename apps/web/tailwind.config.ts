import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#121417",
        paper: "#f7f3ea",
        line: "#d8d1c3",
        moss: "#476a4d",
        copper: "#a85f32",
        signal: "#266f83",
        caution: "#b48924",
        loss: "#9f3f46"
      },
      boxShadow: {
        panel: "0 18px 50px rgba(18, 20, 23, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
