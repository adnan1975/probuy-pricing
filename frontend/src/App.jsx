import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { API_URL } from "./search/constants";
import { fetchAutomatedPricingStatus, fetchStep1Results, openAutomatedPricingStream, startAutomatedPricing } from "./search/searchApi";
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
    toggleWarehouse,
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
  const [isFilterCollapsed, setIsFilterCollapsed] = useState(false);
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
  }, [activePage, canSearch, debouncedTrimmedQuery, page, pageSize, saveSuccessfulSearch, setDetailsState]);

  const visibleResults = useMemo(() => {
    const parseOptionalNumber = (value) => {
      if (value === "" || value === null || value === undefined) {
        return Number.NaN;
      }
      return Number(value);
    };

    const modelFilter = filters.model.trim().toLowerCase();
    const manufacturerModelFilter = filters.manufacturerModel.trim().toLowerCase();
    const selectedUnit = filters.unit;
    const selectedWarehouses = filters.warehouses;
    const listPriceMin = parseOptionalNumber(filters.listPrice.min);
    const listPriceMax = parseOptionalNumber(filters.listPrice.max);
    const distributorCostMin = parseOptionalNumber(filters.distributorCost.min);
    const distributorCostMax = parseOptionalNumber(filters.distributorCost.max);

    return results.filter((item) => {
      const modelMatches = !modelFilter || (item.model || "").toLowerCase().includes(modelFilter);
      const manufacturerModelMatches =
        !manufacturerModelFilter || (item.manufacturer_model || "").toLowerCase().includes(manufacturerModelFilter);
      const listPriceValue = typeof item.price_value === "number" ? item.price_value : Number.NaN;
      const distributorCostValue = typeof item.distributor_cost === "number" ? item.distributor_cost : Number.NaN;
      const listPriceMinMatch = Number.isNaN(listPriceMin) || Number.isNaN(listPriceValue) || listPriceValue >= listPriceMin;
      const listPriceMaxMatch = Number.isNaN(listPriceMax) || Number.isNaN(listPriceValue) || listPriceValue <= listPriceMax;
      const distributorCostMinMatch =
        Number.isNaN(distributorCostMin) || Number.isNaN(distributorCostValue) || distributorCostValue >= distributorCostMin;
      const distributorCostMaxMatch =
        Number.isNaN(distributorCostMax) || Number.isNaN(distributorCostValue) || distributorCostValue <= distributorCostMax;
      const warehouseValue = (item.warehouse || item.warehouse_location || item.location || "").trim().toUpperCase();
      const warehouseMatches =
        selectedWarehouses.length === 0 || selectedWarehouses.some((warehouseCode) => warehouseValue.includes(warehouseCode));
      const itemUnit = (item.unit || "").trim();
      const unitMatches = selectedUnit === "all" || itemUnit === selectedUnit;

      return (
        modelMatches &&
        manufacturerModelMatches &&
        listPriceMinMatch &&
        listPriceMaxMatch &&
        distributorCostMinMatch &&
        distributorCostMaxMatch &&
        warehouseMatches &&
        unitMatches
      );
    });
  }, [filters, results]);

  const unitOptions = useMemo(() => {
    const units = new Set(results.map((item) => (item.unit || "").trim()).filter(Boolean));
    return ["all", ...Array.from(units).sort((a, b) => a.localeCompare(b))];
  }, [results]);
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
    setActiveSuggestionIndex(-1);
    setIsSuggestionOpen(value.trim().length > 0);
  }

  function handlePageSizeChange(value) {
    setPageSize(value);
    resetDetailExpansion();
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

  const dashboardStats = [
    { label: "Catalog SKUs under review", value: "12,481", trend: "+4.2% this week" },
    { label: "Rows with margin risk", value: "318", trend: "-1.8% vs last run" },
    { label: "Price updates published", value: "96", trend: "+12 today" },
    { label: "Connectors healthy", value: "4 / 4", trend: "No outages in 24h" }
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
          <div className="menu-title">PriceSense Internal Console</div>
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
            <div className="topbar">
              <div>
                <div className="tag">Pricing Workspace</div>
                <h1>Merchant-style product search and filter</h1>
                <p>Use SCN pricing data in the main query box, then refine with structured filters for internal price operations.</p>
              </div>
            </div>

            <div className="pricing-layout">
              <aside className={`filter-sidebar panel ${isFilterCollapsed ? "collapsed" : ""}`}>
                <div className="filter-sidebar-header">
                  <h2>Filters</h2>
                  <button
                    type="button"
                    className="filter-collapse-btn"
                    onClick={() => setIsFilterCollapsed((prev) => !prev)}
                  >
                    {isFilterCollapsed ? "Expand" : "Collapse"}
                  </button>
                </div>
                {!isFilterCollapsed && (
                  <>
                    <p className="panel-subtext">Structured filtering for catalog management and pricing governance.</p>

                    <div className="search-box search-box-compact">
                      <div className="typeahead-wrap">
                        <input
                          value={query}
                          onChange={(e) => handleQueryChange(e.target.value)}
                          onFocus={() => setIsSuggestionOpen(query.trim().length > 0)}
                          onBlur={() => {
                            setIsSuggestionOpen(false);
                            setActiveSuggestionIndex(-1);
                          }}
                          onKeyDown={handleQueryKeyDown}
                          placeholder="Search SCN pricing table by model, manufacturer, description, or part number"
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
                    </div>

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
                      <span>Model</span>
                      <input value={draftFilters.model} onChange={(e) => updateFilter("model", e.target.value)} placeholder="Filter model" />
                    </label>

                    <label className="filter-group">
                      <span>Manufacturer Model</span>
                      <input
                        value={draftFilters.manufacturerModel}
                        onChange={(e) => updateFilter("manufacturerModel", e.target.value)}
                        placeholder="Filter manufacturer model"
                      />
                    </label>

                    <div className="filter-group">
                      <span>List Price Range</span>
                      <div className="range-row">
                        <input
                          type="number"
                          value={draftFilters.listPrice.min}
                          onChange={(e) => updateRangeFilter("listPrice", "min", e.target.value)}
                          placeholder="Min"
                        />
                        <input
                          type="number"
                          value={draftFilters.listPrice.max}
                          onChange={(e) => updateRangeFilter("listPrice", "max", e.target.value)}
                          placeholder="Max"
                        />
                      </div>
                    </div>

                    <div className="filter-group">
                      <span>Distributor Cost Range</span>
                      <div className="range-row">
                        <input
                          type="number"
                          value={draftFilters.distributorCost.min}
                          onChange={(e) => updateRangeFilter("distributorCost", "min", e.target.value)}
                          placeholder="Min"
                        />
                        <input
                          type="number"
                          value={draftFilters.distributorCost.max}
                          onChange={(e) => updateRangeFilter("distributorCost", "max", e.target.value)}
                          placeholder="Max"
                        />
                      </div>
                    </div>

                    <div className="filter-group">
                      <span>Warehouse</span>
                      <div className="warehouse-checkboxes">
                        {["VAN", "EDM", "MTL"].map((warehouseCode) => (
                          <label className="checkbox-row" key={warehouseCode}>
                            <input
                              type="checkbox"
                              checked={draftFilters.warehouses.includes(warehouseCode)}
                              onChange={() => toggleWarehouse(warehouseCode)}
                            />
                            <span>{warehouseCode}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <label className="filter-group">
                      <span>Unit</span>
                      <select value={draftFilters.unit} onChange={(e) => updateFilter("unit", e.target.value)}>
                        {unitOptions.map((option) => (
                          <option key={option} value={option}>{option === "all" ? "All units" : option}</option>
                        ))}
                      </select>
                    </label>
                    <button type="button" className="apply-filter-btn" onClick={applyFilters}>
                      Apply Filters
                    </button>
                  </>
                )}
              </aside>

              <div className="pricing-content">
                {!canSearch && (
                  <div className="info-box muted-box">Type a search term to load results.</div>
                )}

                {isTyping && canSearch && (
                  <div className="info-box muted-box">Waiting for typing to pause…</div>
                )}

                <div className="summary-grid">
                  <div className="summary-card"><div className="label">Search term</div><div className="value">{query || "(type a search term)"}</div></div>
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
