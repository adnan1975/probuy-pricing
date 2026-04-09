import { useMemo, useState } from "react";
import { MIN_QUERY_LENGTH } from "./constants";

export function useSearchInput() {
  const [query, setQuery] = useState("");

  const trimmedQuery = useMemo(() => query.trim(), [query]);
  const canSearch = trimmedQuery.length >= MIN_QUERY_LENGTH;

  return {
    query,
    setQuery,
    trimmedQuery,
    canSearch
  };
}
