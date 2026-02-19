# Hooks Standards

- Hooks own state transitions and side effects; components should mostly consume returned state/actions.
- Use stable, serializable React Query keys and avoid object churn in key inputs.
- For map state and events, use `MapViewState` and `PickingInfo` types from `@deck.gl/core`.
- Normalize external payload values before UI use; guard null/undefined and non-finite numbers.
- Keep `useCallback`/`useMemo` dependencies explicit and minimal.
- Every side effect must clean up listeners/timers in the returned cleanup function.
