import type { Metadata } from "next";
import { Source_Serif_4, JetBrains_Mono } from "next/font/google";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import "./globals.css";

const serif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://vibemill.dev"),
  title: "Vibe Mill",
  description:
    "A machine that produces web applications from news headlines and hackathon-style prompts. About five to ten per day.",
  openGraph: {
    title: "Vibe Mill",
    description:
      "A machine that produces web applications from news headlines and hackathon-style prompts.",
    url: "https://vibemill.dev",
    siteName: "Vibe Mill",
    type: "website",
    images: [
      {
        url: "/og.png",
        width: 1200,
        height: 630,
        alt: "Vibe Mill",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Vibe Mill",
    description:
      "A machine that produces web applications from news headlines and hackathon-style prompts.",
    images: ["/og.png"],
  },
};

// Inline theme init: read localStorage / prefers-color-scheme and set the
// `dark` class on <html> before paint, to prevent a flash of light theme
// on dark-mode reloads. This script runs synchronously in <head>.
const themeInitScript = `
(function() {
  try {
    var stored = localStorage.getItem('vm-theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var theme = stored || (prefersDark ? 'dark' : 'light');
    if (theme === 'dark') document.documentElement.classList.add('dark');
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${serif.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
