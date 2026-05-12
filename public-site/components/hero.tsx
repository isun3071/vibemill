export function Hero() {
  return (
    <section
      className="min-h-[calc(100vh-88px)] w-full px-6 sm:px-10 flex flex-col"
      aria-label="Vibe Mill"
    >
      <div className="max-w-3xl mx-auto w-full pt-20 sm:pt-32">
        <blockquote className="font-serif italic text-base sm:text-lg leading-relaxed text-ink-muted dark:text-moon-muted">
          &ldquo;The profession is being dramatically refactored as the bits
          contributed by the programmer are increasingly sparse and between.&rdquo;
          <footer className="not-italic text-sm mt-2 text-right text-ink-faint dark:text-moon-faint">
            &mdash; Andrej Karpathy, 2025
          </footer>
        </blockquote>
      </div>

      <div className="flex-1 flex items-center justify-center px-2">
        <h1 className="max-w-4xl font-serif text-3xl sm:text-5xl leading-tight tracking-tight text-center text-ink dark:text-moon">
          Vibe Mill has removed the last step
          <br />
          in vibe coding: the vibe check.
        </h1>
      </div>

      <div className="pb-10 flex justify-center text-ink-faint dark:text-moon-faint">
        <span aria-hidden className="text-2xl select-none">↓</span>
      </div>
    </section>
  );
}
