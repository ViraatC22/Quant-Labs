"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type ThemeMode = "light" | "dark";

function preferredTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  const saved = window.localStorage.getItem("quant-labs.theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: ThemeMode) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeMode>(() => preferredTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    window.localStorage.setItem("quant-labs.theme", nextTheme);
    applyTheme(nextTheme);
  }

  const dark = theme === "dark";

  return (
    <Button
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={toggleTheme}
      size="icon"
      title={dark ? "Light theme" : "Dark theme"}
      type="button"
      variant="outline"
    >
      {dark ? <Sun aria-hidden="true" size={17} /> : <Moon aria-hidden="true" size={17} />}
    </Button>
  );
}
