export const title = "Hantavirus on the MV Hondius";
export const tagline = "Tracking confirmed cases, vessel position, and health response.";

export const counters = [
  { label: "Confirmed cases", value: 12 },
  { label: "Countries traced", value: 5, sublabel: "of 7 represented onboard" },
  { label: "Days since first case", value: 9 },
];

export const regions: {
  name: string;
  status: "active" | "monitoring" | "resolved" | "unknown";
  value?: number;
}[] = [
  { name: "MV Hondius (vessel)", status: "active", value: 12 },
  { name: "Auckland", status: "monitoring", value: 3 },
  { name: "Suva", status: "monitoring", value: 2 },
  { name: "Sydney", status: "unknown" },
  { name: "Manila", status: "unknown" },
  { name: "Singapore", status: "resolved", value: 0 },
];

export const timelineEvents = [
  {
    date: "2026-04-28",
    title: "First case reported",
    description: "Crew member presents with fever and respiratory distress.",
  },
  {
    date: "2026-04-30",
    title: "Vessel quarantined",
    description: "Auckland port authority denies disembarkation.",
  },
  {
    date: "2026-05-02",
    title: "Confirmed cases reach 8",
    description: "WHO regional office issues advisory.",
  },
  {
    date: "2026-05-06",
    title: "Passenger tracing begins",
    description: "Five countries notified of returning travelers.",
  },
];

export const newsItems = [
  {
    source: "BBC",
    headline: "Cruise ship quarantined off Auckland after virus outbreak",
    url: "https://example.com/news/1",
    publishedAt: "2026-05-01",
  },
  {
    source: "NPR",
    headline: "Hantavirus traced to single passenger boarding in Vanuatu",
    url: "https://example.com/news/2",
    publishedAt: "2026-05-04",
  },
  {
    source: "BBC",
    headline: "WHO confirms 12 cases linked to MV Hondius",
    url: "https://example.com/news/3",
    publishedAt: "2026-05-07",
  },
];
