# Tracker example

ONE possible Tracker app. The orchestrator does not ship this app; it
exists to:

1. Show one shape a free-form Tracker might take (free-form because, per
   GENERATOR.md, the LLM designs the page and chooses its own data shape;
   the chassis only provides layout, footer, Tailwind, and Next.js config).
2. Serve as a build fixture for verifying the chassis itself compiles.

The actual generated apps will look quite different from this one — the
whole point of dropping the chassis primitives was to let the LLM
diverge widely.

## Running

```bash
# From archetypes/tracker/, copy chassis files alongside example/ and build:
cp -r chassis/* example/
cd example
npm install
npm run build
```
