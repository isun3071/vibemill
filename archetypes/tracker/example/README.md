# Tracker example

A working Tracker app filled with example data. The orchestrator does not
ship this app; it exists to:

1. Document the slot file shape (page.tsx + data.ts) the LLM is expected to
   produce, alongside the chassis it must compose with.
2. Serve as a build fixture for verifying the chassis itself compiles.

## Running

```bash
# From archetypes/tracker/, copy chassis files alongside example/ and build:
cp -r chassis/* example/
cd example
npm install
npm run build
```
