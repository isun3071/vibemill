"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    const stored = (localStorage.getItem("vm-theme") as "light" | "dark" | null) ?? null;
    const prefersDark =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    setTheme(stored ?? (prefersDark ? "dark" : "light"));
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("vm-theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  }

  // Render a placeholder until the effect has run; avoids hydration mismatch.
  const label = theme === "dark" ? "switch to light" : "switch to dark";
  const glyph = theme === "dark" ? "◐" : "☾";

  return (
    <button
      onClick={toggle}
      aria-label={label}
      title={label}
      className="text-ink-muted hover:text-ink dark:text-moon-muted dark:hover:text-moon transition-colors text-base leading-none w-6 h-6 inline-flex items-center justify-center"
    >
      <span aria-hidden>{theme === null ? " " : glyph}</span>
    </button>
  );
}
