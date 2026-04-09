import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { API_URL, expectedSources } from "./search/constants";
import { fetchStep1Results } from "./search/searchApi";
import { SearchResultsPanel } from "./search/SearchResultsPanel";
import { useFilterState } from "./search/useFilterState";
import { useProductDetailExpansion } from "./search/useProductDetailExpansion";
import { useSearchInput } from "./search/useSearchInput";

function App() {
  const { query, setQuery, trimmedQuery, canSearch } = useSearchInput();
  const { page, setPage, pageSize, setPageSize, resetFilters } = useFilterState();

  const [results, setResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [perSourceErrors, setPerSourceErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");
  const [totalPages, setTotalPages] = useState(0);
  const [totalResults, setTotalResults] = useState(0);

  const {
    detailsState,
    setDetailsState,
    expandedRows,
    relatedOffersByRow,
    resetDetailExpansion,
    toggleDetails
  } = useProductDetailExpansion({
    apiUrl: API_URL,
    visibleResults: results,
    trimmedQuery
  });

  useEffect(() => {
    const controller = new AbortController();

    async function loadResults() {
      if (!canSearch) {
        setLoading(false);
        setApiError("");
        setResults([]);
        setDetailsState({});
        setAnalysis(null);
        setPerSourceErrors({});
        setTotalPages(0);
        setTotalResults(0);
        return;
      }

      setLoading(true);
      setApiError("");
      try {
        const step1Data = await fetchStep1Results({
          apiUrl: API_URL,
          query: trimmedQuery,
          page,
          pageSize,
          signal: controller.signal
        });

        const scnResults = Array.isArray(step1Data.results) ? step1Data.results : [];
        setResults(scnResults);
        setDetailsState({});
        setAnalysis(step1Data.analysis || null);
        setPerSourceErrors(step1Data.per_source_errors || {});
        setTotalPages(step1Data.total_pages || 0);
        setTotalResults(step1Data.total_results || 0);
      } catch (err) {
        if (err.name !== "AbortError") {
          setApiError(err.message || "Could not load results");
          setResults([]);
          setDetailsState({});
          setAnalysis(null);
          setPerSourceErrors({});
          setTotalPages(0);
          setTotalResults(0);
        }
      } finally {
        setLoading(false);
      }
    }

    loadResults();
    return () => controller.abort();
  }, [canSearch, page, pageSize, setDetailsState, trimmedQuery]);

  const sourceSummary = useMemo(() => {
    const inResults = new Set(results.map((item) => item.source).filter(Boolean));
    return expectedSources.map((source) => ({
      source,
      inResults: inResults.has(source)
    }));
  }, [results]);

  const visibleResults = useMemo(() => results, [results]);

  function formatSuggestedPrice(item, rowIndex) {
    const relatedOffers = relatedOffersByRow[rowIndex] || [];
    const pricedValues = [item, ...relatedOffers]
      .map((offer) => offer.price_value)
      .filter((value) => typeof value === "number");
    const connectorMin = pricedValues.length > 0 ? Math.min(...pricedValues) : null;
    const suggestedPriceValue = typeof connectorMin === "number"
      ? connectorMin
      : (typeof item.suggested_price === "number" ? item.suggested_price : item.price_value);
    if (typeof suggestedPriceValue !== "number") {
      return "N/A";
    }
    return `$${suggestedPriceValue.toFixed(2)}`;
  }

  function formatCurrency(value) {
    if (typeof value !== "number") {
      return "N/A";
    }
    return `$${value.toFixed(2)}`;
  }

  function handleQueryChange(value) {
    setQuery(value);
    resetFilters();
    resetDetailExpansion();
  }

  function handlePageSizeChange(value) {
    setPageSize(value);
    resetDetailExpansion();
  }

  useEffect(() => {
    const connectorOffers = Object.values(detailsState)
      .flatMap((rowState) =>
        Object.values(rowState?.offersBySource || {}).filter(Boolean)
      );
    const pricedResults = [...visibleResults, ...connectorOffers].filter(
      (item) => typeof item.price_value === "number"
    ).length;

    setAnalysis((prev) => {
      if (!prev) {
        return prev;
      }
      return {
        ...prev,
        total_results: visibleResults.length + connectorOffers.length,
        priced_results: pricedResults
      };
    });
    setTotalResults(visibleResults.length + connectorOffers.length);
  }, [detailsState, visibleResults]);

  return (
    <div className="page">
      <div className="container">
        <div className="topbar">
          <div>
            <div className="tag">QuoteSense Pricing Console</div>
            <h1>Primary + Secondary Connector Price Discovery</h1>
            <p>Primary connector results are shown first. Open details to run each secondary connector sequentially.</p>
          </div>

          <div className="help-card">
            <div className="help-title">Configured Sources</div>
            <div className="source-pill-list">
              {sourceSummary.map((item) => (
                <span key={item.source} className={`pill-source ${item.inResults ? "active" : "inactive"}`}>
                  {item.source}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="search-box">
          <input
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="Search by model, description, brand, or part number"
          />
        </div>

        {!canSearch && (
          <div className="info-box muted-box">Type at least 4 characters before searching.</div>
        )}

        <div className="summary-grid">
          <div className="summary-card"><div className="label">Search term</div><div className="value">{query || "(type at least 4 characters)"}</div></div>
          <div className="summary-card"><div className="label">Configured sources</div><div className="value">{expectedSources.length}</div></div>
          <div className="summary-card"><div className="label">Total results</div><div className="value">{analysis?.total_results ?? 0}</div></div>
          <div className="summary-card"><div className="label">Priced results</div><div className="value">{analysis?.priced_results ?? 0}</div></div>
        </div>

        <SearchResultsPanel
          apiError={apiError}
          loading={loading}
          canSearch={canSearch}
          visibleResults={visibleResults}
          analysis={analysis}
          totalResults={totalResults}
          page={page}
          totalPages={totalPages}
          pageSize={pageSize}
          setPage={setPage}
          onPageSizeChange={handlePageSizeChange}
          detailsState={detailsState}
          expandedRows={expandedRows}
          relatedOffersByRow={relatedOffersByRow}
          formatCurrency={formatCurrency}
          formatSuggestedPrice={formatSuggestedPrice}
          onToggleDetails={toggleDetails}
        />

        {Object.keys(perSourceErrors).length > 0 && (
          <div className="panel">
            <h2>Connector status</h2>
            <div className="info-box">
              {Object.entries(perSourceErrors).map(([source, error]) => (
                <div key={source}><strong>{source}:</strong> {error}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
