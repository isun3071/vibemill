import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";

export function Header() {
  return (
    <header className="w-full px-6 sm:px-10 py-6 flex items-center justify-between">
      <Link
        href="/"
        className="font-serif text-lg tracking-tight hover:text-ink-muted dark:hover:text-moon-muted transition-colors"
      >
        Vibe Mill
      </Link>
      <nav className="flex items-center gap-5 text-sm text-ink-muted dark:text-moon-muted">
        <Link href="/about" className="hover:text-ink dark:hover:text-moon transition-colors">
          about
        </Link>
        <Link href="/cemetery" className="hover:text-ink dark:hover:text-moon transition-colors">
          cemetery
        </Link>
        <Link href="/rejected" className="hover:text-ink dark:hover:text-moon transition-colors">
          rejected
        </Link>
        <ThemeToggle />
      </nav>
    </header>
  );
}
