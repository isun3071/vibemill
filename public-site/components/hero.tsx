import Image from "next/image";
import blackCountry from "@/assets/imgs/blackcountry.jpg";

export function Hero() {
  return (
    <section
      className="relative min-h-[calc(100vh-88px)] w-full px-6 sm:px-10 flex flex-col overflow-hidden"
      aria-label="Vibe Mill"
    >
      {/* Backdrop: 19th-century wood engraving of the Black Country
          coal pits + ironworks. Industrial production at landscape scale,
          no humans in the visual subject. Low opacity so the deadpan
          serif type stays the focal layer. Dark-mode invert flips the
          engraving's blacks to lights on the charcoal background. */}
      <Image
        src={blackCountry}
        alt=""
        fill
        sizes="100vw"
        priority
        aria-hidden
        className="object-cover object-center opacity-20 sepia-[0.15] dark:opacity-15 dark:invert dark:sepia-0 pointer-events-none select-none"
      />

      <div className="relative z-10 max-w-3xl mx-auto w-full pt-20 sm:pt-32">
        <blockquote className="font-serif italic text-base sm:text-lg leading-relaxed text-ink-muted dark:text-moon-muted">
          &ldquo;The profession is being dramatically refactored as the bits
          contributed by the programmer are increasingly sparse and between.&rdquo;
          <footer className="not-italic text-sm mt-2 text-right text-ink-faint dark:text-moon-faint">
            &mdash; Andrej Karpathy, October 2025
          </footer>
        </blockquote>
      </div>

      <div className="relative z-10 flex-1 flex items-center justify-center px-2">
        <h1 className="max-w-4xl font-serif text-3xl sm:text-5xl leading-tight tracking-tight text-center text-ink dark:text-moon">
          Vibe Mill has removed the last step<br />in vibe coding: the vibe check.
        </h1>
      </div>

      <div className="relative z-10 pb-10 flex justify-center text-ink-faint dark:text-moon-faint">
        <span aria-hidden className="text-2xl select-none">↓</span>
      </div>
    </section>
  );
}
