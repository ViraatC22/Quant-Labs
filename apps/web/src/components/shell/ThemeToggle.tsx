"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type ThemeMode = "light" | "dark";

function resolveStoredTheme(): ThemeMode {
  const saved = window.localStorage.getItem("quant-labs.theme");
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: ThemeMode) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

export function ThemeToggle() {
  // Start as `null` so the server and the first client render agree (neither
  // knows the user's stored preference). After mount we resolve the real theme
  // and correct the layout's dark-by-default class if the user prefers light.
  const [theme, setTheme] = useState<ThemeMode | null>(null);

  useEffect(() => {
    const resolved = resolveStoredTheme();
    // Setting state on mount is intentional here: the stored/system theme can
    // only be read in the browser, so resolving it after hydration is the
    // SSR-safe way to avoid a server/client mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(resolved);
    applyTheme(resolved);
  }, []);

  function toggleTheme() {
    const nextTheme: ThemeMode = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    window.localStorage.setItem("quant-labs.theme", nextTheme);
    applyTheme(nextTheme);
  }

  const mounted = theme !== null;
  const dark = theme === "dark";

  return (
    <Button
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      disabled={!mounted}
      onClick={toggleTheme}
      size="icon"
      title={dark ? "Light theme" : "Dark theme"}
      type="button"
      variant="outline"
    >
      {!mounted ? (
        // Invisible placeholder keeps the button sized while the theme resolves.
        <Sun aria-hidden="true" className="opacity-0" size={17} />
      ) : dark ? (
        <Sun aria-hidden="true" size={17} />
      ) : (
        <Moon aria-hidden="true" size={17} />
      )}
    </Button>
  );
}
