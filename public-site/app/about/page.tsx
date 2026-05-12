export const metadata = { title: "About — Vibe Mill" };

export default function AboutPage() {
  return (
    <article className="max-w-2xl mx-auto px-6 sm:px-10 py-20 font-serif text-lg leading-relaxed text-ink dark:text-moon">
      <h1 className="text-3xl sm:text-4xl mb-10">About Vibe Mill</h1>

      <p className="mb-6">
        Vibe Mill is a machine that produces web applications from news
        headlines and hackathon-style prompts. It runs every four hours and
        ships about five to ten apps per day. The pipeline runs end to end
        without human review.
      </p>

      <p className="mb-6 text-ink-muted dark:text-moon-muted text-base italic">
        The full thesis is forthcoming.
      </p>
    </article>
  );
}
