// One possible data shape for a Tracker. The LLM is free to define its own
// shape per app — this is just one example for the build fixture.

export const snapshot = {
  title: "Hantavirus on the MV Hondius",
  tagline:
    "Tracking confirmed cases, vessel position, and the public health response across five jurisdictions.",
  stats: [
    { label: "Confirmed cases", value: 12 },
    { label: "Countries traced", value: 5, note: "of 7 onboard" },
    { label: "Days since first case", value: 9 },
    { label: "Quarantine status", value: "Active" },
  ],
  regions: [
    { name: "MV Hondius (vessel)", value: 12 },
    { name: "Auckland", value: 3 },
    { name: "Suva", value: 2 },
    { name: "Sydney", value: 1 },
    { name: "Manila", value: 1 },
  ],
  events: [
    { date: "2026-04-28", text: "First case reported aboard the vessel." },
    { date: "2026-04-30", text: "Auckland port denies disembarkation." },
    { date: "2026-05-02", text: "WHO regional advisory issued." },
    { date: "2026-05-06", text: "Passenger tracing across five countries begins." },
  ],
  news: [
    {
      source: "BBC",
      headline: "Cruise ship quarantined off Auckland after virus outbreak",
      url: "https://example.com/news/1",
    },
    {
      source: "NPR",
      headline: "Hantavirus traced to single passenger boarding in Vanuatu",
      url: "https://example.com/news/2",
    },
    {
      source: "BBC",
      headline: "WHO confirms 12 cases linked to MV Hondius",
      url: "https://example.com/news/3",
    },
  ],
};
