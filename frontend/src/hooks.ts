import { useEffect, useState } from "react";
import { errorMessage } from "./api";

type LoadState<T> = { data: T | null; error: string | null; loading: boolean };

/**
 * Loads data when the component appears and again when `deps` change.
 * While it reloads, the previous data stays visible (no flashing), and an
 * answer that arrives after the component moved on is thrown away (abort).
 */
export function useApi<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ data: null, error: null, loading: true });

  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ ...previous, loading: true, error: null }));
    load(controller.signal).then(
      (data) => setState({ data, error: null, loading: false }),
      (error: unknown) => {
        if (!controller.signal.aborted) setState({ data: null, error: errorMessage(error), loading: false });
      },
    );
    return () => controller.abort();
    // `load` is a new function on every render, so `deps` says when to load again.
  }, deps);

  return state;
}

/** The value, but only after it stopped changing for `delayMs` (for sliders). */
export function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
