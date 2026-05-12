import Link from "next/link";

export function AboutTeaser() {
  return (
    <section className="w-full px-6 sm:px-10 py-20" aria-label="about">
      <div className="max-w-2xl mx-auto">
        <hr className="border-ink/15 dark:border-moon/15 mb-10" />
        <p className="font-serif text-lg leading-relaxed text-ink dark:text-moon">
          Vibe Mill is a machine that produces web applications from news
          headlines and hackathon-style prompts, about five to ten per day. The
          pipeline runs end to end without human review.
        </p>
        <Link
          href="/about"
          className="inline-block mt-6 text-sm text-ink-muted dark:text-moon-muted hover:text-ink dark:hover:text-moon transition-colors"
        >
          read more &rarr;
        </Link>
        <hr className="border-ink/15 dark:border-moon/15 mt-10" />
      </div>
    </section>
  );
}
