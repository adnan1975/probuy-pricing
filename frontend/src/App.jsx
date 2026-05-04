import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { API_URL, SOURCE_MATCH_THRESHOLD_POLICY } from "./search/constants";
import { fetchAutomatedPricingStatus, fetchDashboardCatalogStats, fetchStep1Results, openAutomatedPricingStream, startAutomatedPricing } from "./search/searchApi";
import { SearchResultsPanel } from "./search/SearchResultsPanel";
import { useFilterState } from "./search/useFilterState";
import { useProductDetailExpansion } from "./search/useProductDetailExpansion";
import { useSearchHistoryTypeahead } from "./search/useSearchHistoryTypeahead";
import { useSearchInput } from "./search/useSearchInput";

const topMenuItems = ["Dashboard", "Pricing", "Automated Pricing Test", "Settings"];

function App() {
  const [activePage, setActivePage] = useState("Pricing");
  const { query, setQuery, trimmedQuery, debouncedTrimmedQuery, canSearch } = useSearchInput();
  const {
    page,
    setPage,
    pageSize,
    setPageSize,
    draftFilters,
    filters,
    updateFilter,
    updateRangeFilter,
    updateAttributeFilter,
    applyFilters,
    resetFilters
  } = useFilterState();

  const [results, setResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [perSourceErrors, setPerSourceErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [hasCompletedSearchRequest, setHasCompletedSearchRequest] = useState(false);
  const [apiError, setApiError] = useState("");
  const [totalPages, setTotalPages] = useState(0);
  const [totalResults, setTotalResults] = useState(0);
  const [sortOption, setSortOption] = useState("relevance");
  const [includeLowConfidenceKmsInSuggestedPrice, setIncludeLowConfidenceKmsInSuggestedPrice] = useState(false);
  const [unitSizeFilter, setUnitSizeFilter] = useState("");
  const [facetDistribution, setFacetDistribution] = useState({});
  const [dashboardCatalogStats, setDashboardCatalogStats] = useState({
    total_products: 0,
    total_published_products: 0,
    total_categories: 0,
    channel_counts: {},
    warning: null
  });
  const [autoPricingJobId, setAutoPricingJobId] = useState("");
  const [autoPricingRows, setAutoPricingRows] = useState([]);
  const [autoPricingStatus, setAutoPricingStatus] = useState("idle");
  const [autoPricingError, setAutoPricingError] = useState("");
  const [autoPricingProgress, setAutoPricingProgress] = useState({ processed: 0, total: 0 });
  const {
    searchHistory,
    searchSuggestions,
    setIsSuggestionOpen,
    activeSuggestionIndex,
    setActiveSuggestionIndex,
    showSuggestions,
    saveSuccessfulSearch
  } = useSearchHistoryTypeahead(query);

  const {
    detailsState,
    setDetailsState,
    expandedRows,
    relatedOffersByRow,
    resetDetailExpansion,
    toggleDetails,
    retryDetailsForConnector
  } = useProductDetailExpansion({
    apiUrl: API_URL,
    visibleResults: results,
    trimmedQuery
  });

  useEffect(() => {
    setIsTyping(trimmedQuery !== debouncedTrimmedQuery);
  }, [debouncedTrimmedQuery, trimmedQuery]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadResults() {
      if (!canSearch) {
        setLoading(false);
        setHasCompletedSearchRequest(false);
        setApiError("");
        setResults([]);
        setDetailsState({});
        setAnalysis(null);
        setPerSourceErrors({});
        setTotalPages(0);
        setTotalResults(0);
        setFacetDistribution({});
        return;
      }

      setLoading(true);
      setApiError("");
      try {
        const step1Data = await fetchStep1Results({
          apiUrl: API_URL,
          query: debouncedTrimmedQuery,
          page,
          pageSize,
          filters,
          signal: controller.signal
        });

        const scnResults = Array.isArray(step1Data.results) ? step1Data.results : [];
        setResults(scnResults);
        if (scnResults.length > 0) {
          saveSuccessfulSearch(debouncedTrimmedQuery);
        }
        setDetailsState({});
        setAnalysis(step1Data.analysis || null);
        setPerSourceErrors(step1Data.per_source_errors || {});
        setTotalPages(step1Data.total_pages || 0);
        setTotalResults(step1Data.total_results || 0);
        setFacetDistribution(step1Data.facetDistribution || {});
        setHasCompletedSearchRequest(true);
      } catch (err) {
        if (err.name !== "AbortError") {
          setApiError(err.message || "Could not load results");
          setResults([]);
          setDetailsState({});
          setAnalysis(null);
          setPerSourceErrors({});
          setTotalPages(0);
          setTotalResults(0);
          setFacetDistribution({});
          setHasCompletedSearchRequest(true);
        }
      } finally {
        setLoading(false);
      }
    }

    if (activePage === "Pricing") {
      loadResults();
    }
    return () => controller.abort();
  }, [activePage, canSearch, debouncedTrimmedQuery, filters, page, pageSize, saveSuccessfulSearch, setDetailsState]);

  const visibleResults = useMemo(() => {
    const resultsCopy = [...results];

    if (sortOption === "price_low_high") {
      resultsCopy.sort((left, right) => {
        const leftPrice = typeof left.price_value === "number" ? left.price_value : Number.POSITIVE_INFINITY;
        const rightPrice = typeof right.price_value === "number" ? right.price_value : Number.POSITIVE_INFINITY;
        return leftPrice - rightPrice;
      });
      return resultsCopy;
    }

    if (sortOption === "price_high_low") {
      resultsCopy.sort((left, right) => {
        const leftPrice = typeof left.price_value === "number" ? left.price_value : Number.NEGATIVE_INFINITY;
        const rightPrice = typeof right.price_value === "number" ? right.price_value : Number.NEGATIVE_INFINITY;
        return rightPrice - leftPrice;
      });
      return resultsCopy;
    }

    return resultsCopy;
  }, [results, sortOption]);

  const facetOptions = useMemo(() => {
    const toSortedList = (facetKey) => Object.keys(facetDistribution?.[facetKey] || {}).sort((a, b) => a.localeCompare(b));
    const reserved = new Set(["brand", "manufacturer", "category", "source", "stock_status", "publication_status", "channel_code"]);
    const dynamicAttributeKeys = Object.keys(facetDistribution || {})
      .filter((key) => !reserved.has(key))
      .sort((a, b) => a.localeCompare(b));

    return {
      brand: toSortedList("brand"),
      manufacturer: toSortedList("manufacturer"),
      category: toSortedList("category"),
      source: toSortedList("source"),
      stock_status: toSortedList("stock_status"),
      publication_status: toSortedList("publication_status"),
      channel_code: toSortedList("channel_code"),
      dynamicAttributeKeys
    };
  }, [facetDistribution]);

  function formatSuggestedPrice(item, rowIndex) {
    const rowDetails = detailsState[String(rowIndex)] || {};
    const offersBySource = rowDetails.offersBySource || {};
    const matchBySource = rowDetails.matchBySource || {};
    const kmsThreshold = SOURCE_MATCH_THRESHOLD_POLICY["KMS Tools"]?.minAcceptableMatchPercentage || 0;

    const eligibleConnectorOffers = Object.entries(offersBySource)
      .filter(([, offer]) => Boolean(offer))
      .filter(([source]) => {
        if (source !== "KMS Tools") {
          return true;
        }
        if (includeLowConfidenceKmsInSuggestedPrice) {
          return true;
        }
        const match = matchBySource[source];
        const matchPercentage = Number(match?.matchPercentage) || 0;
        return matchPercentage >= kmsThreshold;
      })
      .map(([, offer]) => offer);

    const pricedValues = [item, ...eligibleConnectorOffers]
      .map((offer) => offer?.price_value)
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
    setActiveSuggestionIndex(-1);
    setIsSuggestionOpen(value.trim().length > 0);
  }

  function handleSearchSubmit(event) {
    event.preventDefault();
    const nextQuery = query.trim();
    if (!nextQuery) {
      return;
    }
    setQuery(nextQuery);
    setIsSuggestionOpen(false);
    setActiveSuggestionIndex(-1);
    setPage(1);
  }

  function handlePageSizeChange(value) {
    setPageSize(value);
    resetDetailExpansion();
  }

  function resetSearchViewState() {
    setPage(1);
    resetDetailExpansion();
  }

  function handleClearFiltersRecovery() {
    resetFilters();
    setUnitSizeFilter("");
    resetSearchViewState();
  }

  function handleUseExampleQueryRecovery() {
    setQuery("DEWALT FLEXVOLT grinder DCG418B");
    resetFilters();
    resetSearchViewState();
    setActiveSuggestionIndex(-1);
    setIsSuggestionOpen(false);
  }

  function handleHistorySelection(value) {
    setQuery(value);
    resetFilters();
    resetDetailExpansion();
    setActiveSuggestionIndex(-1);
    setIsSuggestionOpen(false);
  }

  function handleQueryKeyDown(event) {
    if (!showSuggestions) {
      if (event.key === "Escape") {
        setIsSuggestionOpen(false);
        setActiveSuggestionIndex(-1);
      }
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveSuggestionIndex((currentIndex) =>
        currentIndex < searchSuggestions.length - 1 ? currentIndex + 1 : 0
      );
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveSuggestionIndex((currentIndex) =>
        currentIndex > 0 ? currentIndex - 1 : searchSuggestions.length - 1
      );
      return;
    }

    if (event.key === "Enter" && activeSuggestionIndex >= 0) {
      event.preventDefault();
      handleHistorySelection(searchSuggestions[activeSuggestionIndex]);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setIsSuggestionOpen(false);
      setActiveSuggestionIndex(-1);
    }
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

  useEffect(() => {
    if (activePage !== "Dashboard") {
      return;
    }

    const controller = new AbortController();
    fetchDashboardCatalogStats({ apiUrl: API_URL, signal: controller.signal })
      .then((payload) => {
        setDashboardCatalogStats({
          total_products: Number(payload?.total_products || 0),
          total_published_products: Number(payload?.total_published_products || 0),
          total_categories: Number(payload?.total_categories || 0),
          channel_counts: payload?.channel_counts && typeof payload.channel_counts === "object" ? payload.channel_counts : {},
          warning: payload?.warning || null
        });
      })
      .catch(() => {
        setDashboardCatalogStats((previous) => ({
          ...previous,
          warning: "Could not load dashboard stats from Supabase."
        }));
      });

    return () => controller.abort();
  }, [activePage]);

  const dashboardStats = [
    {
      label: "Total published products",
      value: dashboardCatalogStats.total_published_products.toLocaleString(),
      trend: "Loaded from Supabase catalog"
    },
    {
      label: "Total categories",
      value: dashboardCatalogStats.total_categories.toLocaleString(),
      trend: "Unique categories in Supabase"
    },
    {
      label: "Shopify products",
      value: Number(dashboardCatalogStats.channel_counts?.shopify || 0).toLocaleString(),
      trend: "Products mapped to channel_code = shopify"
    },
    {
      label: "Method products",
      value: Number(dashboardCatalogStats.channel_counts?.method || 0).toLocaleString(),
      trend: "Products mapped to channel_code = method"
    }
  ];

  useEffect(() => {
    if (activePage !== "Automated Pricing Test" || !autoPricingJobId) {
      return undefined;
    }

    let eventSource = null;
    let isActive = true;

    const bootstrapStatus = async () => {
      try {
        const payload = await fetchAutomatedPricingStatus({
          apiUrl: API_URL,
          jobId: autoPricingJobId
        });
        if (!isActive) {
          return;
        }
        setAutoPricingRows(Array.isArray(payload.rows) ? payload.rows : []);
        setAutoPricingStatus(payload.status || "running");
        setAutoPricingProgress({
          processed: payload.processed_items || 0,
          total: payload.total_items || 0
        });
      } catch (err) {
        if (isActive) {
          setAutoPricingError(err.message || "Could not fetch automated pricing progress");
        }
      }
    };

    bootstrapStatus();

    eventSource = openAutomatedPricingStream({ apiUrl: API_URL, jobId: autoPricingJobId });

    eventSource.addEventListener("row", (event) => {
      const payload = JSON.parse(event.data || "{}");
      if (!payload.row) {
        return;
      }
      setAutoPricingRows((previousRows) => [...previousRows, payload.row]);
      setAutoPricingStatus("running");
      setAutoPricingProgress({
        processed: payload.processed_items || 0,
        total: payload.total_items || 0
      });
    });

    eventSource.addEventListener("done", (event) => {
      const payload = JSON.parse(event.data || "{}");
      setAutoPricingStatus("completed");
      setAutoPricingProgress({
        processed: payload.processed_items || 0,
        total: payload.total_items || 0
      });
      eventSource?.close();
    });

    eventSource.onerror = () => {
      if (!isActive) {
        return;
      }
      setAutoPricingError("Live stream interrupted. Showing latest processed rows.");
      eventSource?.close();
    };

    return () => {
      isActive = false;
      eventSource?.close();
    };
  }, [activePage, autoPricingJobId]);

  async function handleAutomatedPricingStart() {
    setAutoPricingError("");
    setAutoPricingRows([]);
    setAutoPricingStatus("starting");
    setAutoPricingProgress({ processed: 0, total: 100 });
    try {
      const payload = await startAutomatedPricing({ apiUrl: API_URL, limit: 100 });
      setAutoPricingJobId(payload.job_id);
      setAutoPricingStatus(payload.status || "running");
      setAutoPricingProgress({ processed: 0, total: payload.total_items || 100 });
    } catch (err) {
      setAutoPricingStatus("error");
      setAutoPricingError(err.message || "Could not start automated pricing");
    }
  }

  function formatMaybeCurrency(value) {
    if (typeof value !== "number") {
      return "N/A";
    }
    return `$${value.toFixed(2)}`;
  }

  return (
    <div className="page">
      <div className="container">
        <nav className="menu-bar">
          <div className="menu-title">Price Sense Admin Console</div>
          <div className="menu-items">
            {topMenuItems.map((item) => (
              <button
                key={item}
                type="button"
                className={`menu-item ${activePage === item ? "active" : ""}`}
                onClick={() => setActivePage(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </nav>

        {activePage === "Dashboard" && (
          <section>
            <div className="topbar dashboard-header">
              <div>
                <div className="tag">Operations Snapshot</div>
                <h1>Pricing performance dashboard</h1>
                <p>Track pricing health, margin exposure, and publishing cadence for internal merchandising workflows.</p>
              </div>
            </div>
            {dashboardCatalogStats.warning && (
              <div className="panel" role="status">
                <p className="panel-subtext">{dashboardCatalogStats.warning}</p>
              </div>
            )}
            <div className="summary-grid four-cols">
              {dashboardStats.map((stat) => (
                <div className="summary-card" key={stat.label}>
                  <div className="label">{stat.label}</div>
                  <div className="value">{stat.value}</div>
                  <div className="trend">{stat.trend}</div>
                </div>
              ))}
            </div>
            <div className="panel">
              <h2>Channel stats</h2>
              <p className="panel-subtext">Totals grouped by <code>channel_code</code> from the loaded catalog facets.</p>
              <div className="detail-grid">
                <div><strong>Total channel products</strong><div>{Object.values(dashboardCatalogStats.channel_counts || {}).reduce((total, count) => total + Number(count || 0), 0).toLocaleString()}</div></div>
                <div><strong>Tracked channels</strong><div>{Object.keys(dashboardCatalogStats.channel_counts || {}).length}</div></div>
              </div>
              {Object.keys(dashboardCatalogStats.channel_counts || {}).length > 0 ? (
                <div className="details-grid">
                  {Object.entries(dashboardCatalogStats.channel_counts || {})
                    .sort((left, right) => right[1] - left[1])
                    .map(([channel, count]) => (
                      <div className="details-card" key={channel}>
                        <div className="table-strong">{channel}</div>
                        <div className="table-sub">{count.toLocaleString()} products</div>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="panel-subtext">Run a product search in Pricing to populate channel-level dashboard stats.</p>
              )}
            </div>
            <div className="panel">
              <h2>30-day distributor cost vs list price variance</h2>
              <p className="panel-subtext">Mock report preview for upcoming analytics integration.</p>
              <div className="mock-graph" aria-label="mock pricing variance graph">
                {[42, 35, 46, 40, 52, 48, 55, 44, 58, 61, 53, 49].map((height, index) => (
                  <div key={index} className="graph-col-wrap">
                    <div className="graph-col" style={{ height: `${height * 3}px` }} />
                  </div>
                ))}
              </div>
            </div>
            <div className="panel">
              <h2>Recommended reports</h2>
              <div className="details-grid">
                <div className="details-card"><div className="table-strong">Top 50 margin compression SKUs</div><div className="table-sub">Monitor list vs cost spread across warehouse-bearing items.</div></div>
                <div className="details-card"><div className="table-strong">Manufacturer model conflict report</div><div className="table-sub">Catch duplicate or ambiguous manufacturer model mappings.</div></div>
                <div className="details-card"><div className="table-strong">Unit-level normalization audit</div><div className="table-sub">Review SKU records with inconsistent units before publishing.</div></div>
              </div>
            </div>
          </section>
        )}

        {activePage === "Pricing" && (
          <section>
            <div className="panel search-hero-panel">
              <form className="search-hero-form" onSubmit={handleSearchSubmit}>
                <label htmlFor="product-search-input" className="search-hero-label">Search products</label>
                <div className="search-hero-input-row">
                  <div className="typeahead-wrap">
                    <input
                      id="product-search-input"
                      value={query}
                      onChange={(e) => handleQueryChange(e.target.value)}
                      onFocus={() => setIsSuggestionOpen(query.trim().length > 0)}
                      onBlur={() => {
                        setIsSuggestionOpen(false);
                        setActiveSuggestionIndex(-1);
                      }}
                      onKeyDown={handleQueryKeyDown}
                      placeholder="Search by model, SKU, brand, size, or description…"
                      aria-autocomplete="list"
                      aria-expanded={showSuggestions}
                      aria-controls="search-typeahead-list"
                    />
                    {showSuggestions && (
                      <ul id="search-typeahead-list" className="typeahead-list" role="listbox">
                        {searchSuggestions.map((term, index) => (
                          <li key={term.toLowerCase()} role="option" aria-selected={index === activeSuggestionIndex}>
                            <button
                              type="button"
                              className={`typeahead-item ${index === activeSuggestionIndex ? "active" : ""}`}
                              onMouseDown={(event) => {
                                event.preventDefault();
                                handleHistorySelection(term);
                              }}
                              onMouseEnter={() => setActiveSuggestionIndex(index)}
                            >
                              {term}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <button type="submit" className="apply-filter-btn search-submit-btn">Search</button>
                </div>
              </form>
              <div className="search-helper-text">
                Example searches: DEWALT FLEXVOLT grinder DCG418B · 3M SecureFit SF201AF · Makita circular saw blade 7-1/4
              </div>
            </div>

            <div className="pricing-layout modern-pricing-layout">
              <aside className="filter-sidebar panel">
                <div className="filter-sidebar-header">
                  <h2>Refine Results</h2>
                </div>
                <>
                  <p className="panel-subtext">Use quick filters to narrow product cards without changing search connectors.</p>

                  {searchHistory.length > 0 && (
                    <div className="search-history" aria-label="recent searches">
                      <div className="search-history-label">Recent searches</div>
                      <div className="search-history-list">
                        {searchHistory.map((term) => (
                          <button
                            type="button"
                            key={term.toLowerCase()}
                            className="search-history-chip"
                            onClick={() => handleHistorySelection(term)}
                          >
                            {term}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <label className="filter-group">
                    <span>Brand</span>
                    <input value={draftFilters.brand} onChange={(e) => updateFilter("brand", e.target.value)} placeholder="e.g. DEWALT" />
                  </label>

                    <label className="filter-group">
                      <span>Manufacturer</span>
                      <input
                        value={draftFilters.manufacturer}
                        onChange={(e) => updateFilter("manufacturer", e.target.value)}
                        placeholder="e.g. 3M"
                      />
                    </label>

                    <label className="filter-group">
                      <span>Unit / size</span>
                      <input
                        value={unitSizeFilter}
                        onChange={(e) => setUnitSizeFilter(e.target.value)}
                        placeholder="e.g. 7-1/4 in, 4.5 in, 1 gal"
                        aria-label="Filter by unit or size"
                      />
                    </label>

                    <label className="filter-group">
                      <span>Category</span>
                      <select value={draftFilters.category} onChange={(e) => updateFilter("category", e.target.value)}>
                        <option value="">All categories</option>
                        {facetOptions.category.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>

                    <label className="filter-group">
                      <span>Source</span>
                      <select value={draftFilters.source} onChange={(e) => updateFilter("source", e.target.value)}>
                        <option value="">All sources</option>
                        {facetOptions.source.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>

                    <label className="filter-group">
                      <span>Availability</span>
                      <select value={draftFilters.stock_status} onChange={(e) => updateFilter("stock_status", e.target.value)}>
                        <option value="">Any availability</option>
                        {facetOptions.stock_status.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>

                    <label className="filter-group">
                      <span>Published</span>
                      <select value={draftFilters.publication_status} onChange={(e) => updateFilter("publication_status", e.target.value)}>
                        <option value="">Any status</option>
                        {facetOptions.publication_status.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>

                    <label className="filter-group">
                      <span>Channel</span>
                      <select value={draftFilters.channel_code} onChange={(e) => updateFilter("channel_code", e.target.value)}>
                        <option value="">All channels</option>
                        {facetOptions.channel_code.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>

                    <div className="filter-group">
                      <span>Price Range</span>
                      <div className="range-row">
                        <input
                          type="number"
                          value={draftFilters.price.min}
                          onChange={(e) => updateRangeFilter("price", "min", e.target.value)}
                          placeholder="Min"
                        />
                        <input
                          type="number"
                          value={draftFilters.price.max}
                          onChange={(e) => updateRangeFilter("price", "max", e.target.value)}
                          placeholder="Max"
                        />
                      </div>
                    </div>

                    {facetOptions.dynamicAttributeKeys.map((attributeKey) => (
                      <label className="filter-group" key={attributeKey}>
                        <span>{attributeKey}</span>
                        <select
                          value={draftFilters.attributes?.[attributeKey] || ""}
                          onChange={(e) => updateAttributeFilter(attributeKey, e.target.value)}
                        >
                          <option value="">All</option>
                          {Object.keys(facetDistribution?.[attributeKey] || {}).sort((a, b) => a.localeCompare(b)).map((option) => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      </label>
                    ))}

                  <button type="button" className="apply-filter-btn" onClick={applyFilters}>
                    Apply Filters
                  </button>
                  {/* TODO: Unit/size field is currently UI-only until backend exposes a dedicated normalized unit facet. */}
                </>
              </aside>

              <div className="pricing-content">
                {!canSearch && (
                  <div className="info-box muted-box">Type a search term to load results.</div>
                )}

                {isTyping && canSearch && (
                  <div className="info-box muted-box">Waiting for typing to pause…</div>
                )}

                <div className="results-toolbar">
                  <div className="results-toolbar-note">
                    {/* TODO: Wire recently updated sorting to backend once updated timestamps are included in search payload. */}
                    Filters and sort are applied without changing existing API behavior.
                  </div>
                  <label className="filter-group results-toolbar-sort">
                    <span>Sort by</span>
                    <select value={sortOption} onChange={(e) => setSortOption(e.target.value)} aria-label="Sort search results">
                      <option value="relevance">Relevance</option>
                      <option value="price_low_high">Price low to high</option>
                      <option value="price_high_low">Price high to low</option>
                      <option value="recently_updated">Recently updated</option>
                    </select>
                  </label>
                  <label className="filter-group results-toolbar-sort">
                    <span>Suggested price policy</span>
                    <input
                      type="checkbox"
                      checked={includeLowConfidenceKmsInSuggestedPrice}
                      onChange={(e) => setIncludeLowConfidenceKmsInSuggestedPrice(e.target.checked)}
                    />
                    Include low-confidence KMS offers
                  </label>
                </div>

                <div className="summary-grid search-summary-grid">
                  <div className="summary-card"><div className="label">Search term</div><div className="value">{query || "(type a search term)"}</div></div>
                  <div className="summary-card"><div className="label">Sort</div><div className="value">{sortOption.replaceAll("_", " ")}</div></div>
                  <div className="summary-card"><div className="label">Page results</div><div className="value">{results.length}</div></div>
                  <div className="summary-card"><div className="label">Filtered results</div><div className="value">{visibleResults.length}</div></div>
                  <div className="summary-card"><div className="label">Priced results</div><div className="value">{analysis?.priced_results ?? 0}</div></div>
                </div>

                <SearchResultsPanel
                  apiError={apiError}
                  loading={loading}
                  activeQuery={debouncedTrimmedQuery}
                  canSearch={canSearch}
                  hasActiveSearch={canSearch}
                  hasCompletedSearchRequest={hasCompletedSearchRequest}
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
                  onRetryConnector={retryDetailsForConnector}
                  onClearFilters={handleClearFiltersRecovery}
                  onUseExampleQuery={handleUseExampleQueryRecovery}
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
          </section>
        )}

        {activePage === "Settings" && (
          <section>
            <div className="topbar dashboard-header">
              <div>
                <div className="tag">Administration</div>
                <h1>Settings</h1>
                <p>Manage internal pricing workspace preferences, connector defaults, and publication controls.</p>
              </div>
            </div>
            <div className="panel">
              <h2>Workspace settings (mock)</h2>
              <div className="details-grid">
                <div className="details-card"><div className="table-strong">Default page size</div><div className="table-sub">25 rows (current)</div></div>
                <div className="details-card"><div className="table-strong">Currency display</div><div className="table-sub">CAD</div></div>
                <div className="details-card"><div className="table-strong">Auto-refresh connector prices</div><div className="table-sub">Disabled</div></div>
              </div>
            </div>
          </section>
        )}

        {activePage === "Automated Pricing Test" && (
          <section>
            <div className="topbar">
              <div>
                <div className="tag">Automation Test</div>
                <h1>Automated Pricing Processing Run</h1>
                <p>Run the first 100 SCN items and stream processed rows after all connector results are available.</p>
              </div>
              <button type="button" className="apply-filter-btn" onClick={handleAutomatedPricingStart}>
                Test Automated Pricing
              </button>
            </div>

            <div className="summary-grid two-cols compact-grid">
              <div className="summary-card">
                <div className="label">Run status</div>
                <div className="value">{autoPricingStatus}</div>
              </div>
              <div className="summary-card">
                <div className="label">Processed items</div>
                <div className="value">{autoPricingProgress.processed} / {autoPricingProgress.total}</div>
              </div>
            </div>

            {autoPricingError && <div className="error-box">{autoPricingError}</div>}

            <div className="panel retailer-table-wrap">
              <table className="retailer-table">
                <thead>
                  <tr>
                    <th>Item Name</th>
                    <th>Model</th>
                    <th>Description</th>
                    <th>KMS Tools Price</th>
                    <th>Other Connector Price</th>
                    <th>Final Price</th>
                    <th>Published to Shopify</th>
                    <th>Published to Method</th>
                  </tr>
                </thead>
                <tbody>
                  {autoPricingRows.length === 0 && (
                    <tr>
                      <td colSpan={8}>No processed rows yet. Start the run to stream results.</td>
                    </tr>
                  )}
                  {autoPricingRows.map((row, index) => (
                    <tr key={`${row.model}-${index}`}>
                      <td>{row.item_name || "N/A"}</td>
                      <td>{row.model || "N/A"}</td>
                      <td>{row.description || "N/A"}</td>
                      <td>{formatMaybeCurrency(row.kms_tools_price)}</td>
                      <td>{formatMaybeCurrency(row.other_connector_price)}</td>
                      <td>{formatMaybeCurrency(row.final_price)}</td>
                      <td>{row.published_to_shopify ? "True" : "False"}</td>
                      <td>{row.published_to_method ? "True" : "False"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

export default App;
