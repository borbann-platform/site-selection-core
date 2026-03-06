# Routes Standards

- Route files orchestrate data loading and layout composition; avoid embedding heavy business logic.
- Keep route-level typing strict; do not use `@ts-nocheck` in route files.
- Gate data queries with `enabled` and use practical `staleTime` values for UX stability.
- Prefer lazy loading for large route-only panels/reports.
- For map-enabled routes, use shared map container contracts and DeckGL-native event typing.
- Preserve existing URL/search param behavior when refactoring route internals.
