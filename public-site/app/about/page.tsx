export const metadata = { title: "About — Vibe Mill" };

export default function AboutPage() {
  return (
    <article className="max-w-2xl mx-auto px-6 sm:px-10 py-20 font-serif text-lg leading-relaxed text-ink dark:text-moon">
      <h1 className="text-3xl sm:text-4xl mb-10">About Vibe Mill</h1>

      <blockquote className="border-l-2 border-ink/20 dark:border-moon/20 pl-4 mb-10 text-ink-muted dark:text-moon-muted italic text-base">
        “The profession is being dramatically refactored as the bits
        contributed by the programmer are increasingly sparse and between.”
        <span className="block not-italic mt-2 text-sm">— Andrej Karpathy, October 2025</span>
      </blockquote>

      <p className="mb-6">
        Vibe Mill is a machine that produces web applications from news
        headlines and hackathon-style prompts. It runs every four hours and
        ships five to ten apps per day. The pipeline runs end to end without
        human review. Apps cost between five and seventy cents to produce,
        depending on tier. The average is about thirty cents.
      </p>

      <p className="mb-6">
        Each app is published as a GitHub repo, a live deployment, and a
        screenshot. Every artifact discloses, in its README and footer, that
        it was produced by an automated pipeline. After twenty-one days each
        app is retired to a cemetery with its cause of death and total cost
        recorded. The mill does not promise quality. It does not promise
        relevance. It ships.
      </p>

      <p className="mb-6">
        Major League Hacking, which governs most US college hackathons,
        publishes its judging rules openly. The rules explicitly exclude
        code quality and idea novelty from scoring. Broken demos are
        explicitly accepted. Meanwhile, career advice infrastructure tells
        juniors to put hackathon work on their resumes, hiring managers
        report seeking hackathon experience as signal, and resume guides
        teach juniors to frame the roughness of their submissions as grit.
      </p>

      <p className="mb-6">
        Vibe Mill produces artifacts under conditions that match what MLH
        judges accept. The conditions match because the conditions are
        documented. The artifacts are operationally indistinguishable from
        what a sub-prize-winning team ships in thirty-six hours. The mill
        produces about fifteen of them in the same window for roughly a
        dollar in tokens.
      </p>

      <p className="mb-6">
        The kid pulling an all-nighter in a Cambridge dorm room, watching
        their backend die ten minutes before submission, is not the joke.
        The kid is the person being lied to. The career advice told them
        to do this. The university told them to put it on their resume.
        The hiring managers told them it was signal. Vibe Mill exists to
        make the lie undeniable.
      </p>

      <p className="mb-10">
        The longer version of this argument lives in{" "}
        <a
          href="https://github.com/isun3071/vibemill/blob/main/THESIS.md"
          target="_blank"
          rel="noopener noreferrer"
          className="underline decoration-ink/30 dark:decoration-moon/30 underline-offset-4 hover:decoration-ink dark:hover:decoration-moon"
        >
          THESIS.md
        </a>
        . The operational rules that keep the mill from drifting toward a
        productivity tool live in{" "}
        <a
          href="https://github.com/isun3071/vibemill/blob/main/ANTI_PATTERNS.md"
          target="_blank"
          rel="noopener noreferrer"
          className="underline decoration-ink/30 dark:decoration-moon/30 underline-offset-4 hover:decoration-ink dark:hover:decoration-moon"
        >
          ANTI_PATTERNS.md
        </a>
        . Both are public on purpose. A clone that strips the cemetery,
        the disclaimer, and the cost ledger produces a different system.
        It does not produce Vibe Mill.
      </p>

      <p className="text-ink-muted dark:text-moon-muted text-base">
        Vibe Mill itself was vibecoded. The orchestrator was built with
        Claude Code in pair-programming sessions; the thesis was written
        in conversation with Claude. The orchestrator’s design involved a
        human. The artifacts the orchestrator produces involve none. The
        distinction is the entire point.
      </p>
    </article>
  );
}
