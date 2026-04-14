import { useCallback, useMemo, useState } from "react";
import { getRankedSuggestions, getSearchHistory, saveSearchTerm } from "./searchHistoryService";

export function useSearchHistoryTypeahead(query) {
  const [searchHistory, setSearchHistory] = useState(() => getSearchHistory());
  const [isSuggestionOpen, setIsSuggestionOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);

  const searchSuggestions = useMemo(
    () => getRankedSuggestions(query, searchHistory),
    [query, searchHistory]
  );

  const showSuggestions = isSuggestionOpen && query.trim().length > 0 && searchSuggestions.length > 0;

  const saveSuccessfulSearch = useCallback((term) => {
    setSearchHistory(saveSearchTerm(term));
  }, []);

  return {
    searchHistory,
    searchSuggestions,
    isSuggestionOpen,
    setIsSuggestionOpen,
    activeSuggestionIndex,
    setActiveSuggestionIndex,
    showSuggestions,
    saveSuccessfulSearch
  };
}
