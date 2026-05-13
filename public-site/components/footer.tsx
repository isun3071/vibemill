export function Footer() {
  return (
    <footer className="w-full px-6 sm:px-10 py-10 mt-20 border-t border-ink/10 dark:border-moon/10 text-sm">
      <div className="max-w-5xl mx-auto flex flex-col gap-2">
        <div className="text-ink dark:text-moon">Vibe Mill · 2026</div>
        <div>
          <a
            href="mailto:iansun20@gmail.com"
            className="text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon transition-colors"
          >
            iansun20@gmail.com
          </a>
        </div>
        <div className="text-ink-faint dark:text-moon-faint text-xs flex gap-4">
          <a
            href="https://www.linkedin.com/in/iansun20"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-ink dark:hover:text-moon transition-colors"
          >
            linkedin
          </a>
          <a
            href="https://isun3071.github.io"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-ink dark:hover:text-moon transition-colors"
          >
            portfolio
          </a>
        </div>
      </div>
    </footer>
  );
}
