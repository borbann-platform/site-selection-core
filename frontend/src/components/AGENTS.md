# Components Standards

- Keep components presentational when possible; move cross-feature logic into hooks.
- Prefer explicit TypeScript types over `any` and do not use `@ts-nocheck` in hand-written files.
- For DeckGL integration, use core types from `@deck.gl/core` and prop types from shared wrappers.
- Keep map click/tooltip handlers defensive: guard `info.object` shape before accessing fields.
- Lazy-load large optional UI/report dependencies rather than importing at module top.
- Preserve existing behavior during refactors; treat visual or interaction changes as separate work.
