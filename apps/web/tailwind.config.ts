import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: {
        "2xl": "1280px"
      }
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))"
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))"
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))"
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))"
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))"
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))"
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))"
        },
        ink: "hsl(var(--ink))",
        paper: "hsl(var(--paper))",
        line: "hsl(var(--line))",
        moss: "hsl(var(--moss))",
        copper: "hsl(var(--copper))",
        signal: "hsl(var(--signal))",
        caution: "hsl(var(--caution))",
        loss: "hsl(var(--loss))"
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)"
      },
      boxShadow: {
        panel: "var(--shadow-panel)",
        glow: "var(--shadow-glow)"
      },
      keyframes: {
        "grid-pan": {
          "0%": { transform: "translate3d(0, 0, 0)" },
          "100%": { transform: "translate3d(44px, 44px, 0)" }
        },
        shine: {
          "0%": { backgroundPosition: "200% center" },
          "100%": { backgroundPosition: "-200% center" }
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "0.58" },
          "50%": { opacity: "0.92" }
        }
      },
      animation: {
        "grid-pan": "grid-pan 18s linear infinite",
        shine: "shine 6s linear infinite",
        "pulse-soft": "pulse-soft 4s ease-in-out infinite"
      }
    }
  },
  plugins: []
};

export default config;
