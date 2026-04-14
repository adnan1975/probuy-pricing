import { useEffect, useMemo, useState } from "react";
import { MIN_QUERY_LENGTH } from "./constants";

const QUERY_DEBOUNCE_MS = 400;

export function useSearchInput() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedQuery(query);
    }, QUERY_DEBOUNCE_MS);

    return () => window.clearTimeout(timeoutId);
  }, [query]);

  const trimmedQuery = useMemo(() => query.trim(), [query]);
  const debouncedTrimmedQuery = useMemo(() => debouncedQuery.trim(), [debouncedQuery]);
  const canSearch = debouncedTrimmedQuery.length >= MIN_QUERY_LENGTH;

  return {
    query,
    setQuery,
    trimmedQuery,
    debouncedTrimmedQuery,
    canSearch
  };
}
