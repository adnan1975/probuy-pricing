const SEARCH_HISTORY_KEY = "pricing_search_history";

export function normalizeSearchTerm(term) {
  if (typeof term !== "string") {
    return "";
  }
  return term.trim().replace(/\s+/g, " ");
}

function readHistory() {
  try {
    const raw = window.localStorage.getItem(SEARCH_HISTORY_KEY);
    const parsed = JSON.parse(raw || "[]");
    return Array.isArray(parsed) ? parsed.filter((value) => typeof value === "string") : [];
  } catch {
    return [];
  }
}

function writeHistory(history) {
  window.localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history));
}

export function saveSearchTerm(term) {
  const normalizedTerm = normalizeSearchTerm(term);
  if (!normalizedTerm) {
    return getSearchHistory();
  }

  const lowerNormalized = normalizedTerm.toLowerCase();
  const deduped = readHistory().filter((existingTerm) => existingTerm.toLowerCase() !== lowerNormalized);
  const nextHistory = [normalizedTerm, ...deduped];

  writeHistory(nextHistory);
  return nextHistory;
}

export function getSearchHistory() {
  return readHistory();
}

export function getRankedSuggestions(query, historyTerms) {
  const normalizedQuery = normalizeSearchTerm(query).toLowerCase();
  if (!normalizedQuery || !Array.isArray(historyTerms)) {
    return [];
  }

  const prefixMatches = [];
  const substringMatches = [];

  historyTerms.forEach((term) => {
    if (typeof term !== "string") {
      return;
    }

    const normalizedTerm = normalizeSearchTerm(term);
    if (!normalizedTerm) {
      return;
    }

    const lowerTerm = normalizedTerm.toLowerCase();
    if (lowerTerm.startsWith(normalizedQuery)) {
      prefixMatches.push(normalizedTerm);
    } else if (lowerTerm.includes(normalizedQuery)) {
      substringMatches.push(normalizedTerm);
    }
  });

  return [...prefixMatches, ...substringMatches];
}
