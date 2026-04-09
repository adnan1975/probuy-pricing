import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { API_URL } from "./search/constants";
import { fetchStep1Results } from "./search/searchApi";
import { SearchResultsPanel } from "./search/SearchResultsPanel";
import { useFilterState } from "./search/useFilterState";
import { useProductDetailExpansion } from "./search/useProductDetailExpansion";
import { useSearchInput } from "./search/useSearchInput";

const topMenuItems = ["Dashboard", "Pricing", "Settings"];

function App() {
  const [activePage, setActivePage] = useState("Pricing");
  const { query, setQuery, trimmedQuery, canSearch } = useSearchInput();
  const {
    page,
    setPage,
    pageSize,
    setPageSize,
    filters,
    updateFilter,
    updateRangeFilter,
    resetFilters
  } = useFilterState();

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

    if (activePage === "Pricing") {
      loadResults();
    }
    return () => controller.abort();
  }, [activePage, canSearch, page, pageSize, setDetailsState, trimmedQuery]);

  const visibleResults = useMemo(() => {
    const modelFilter = filters.model.trim().toLowerCase();
    const manufacturerModelFilter = filters.manufacturerModel.trim().toLowerCase();
    const selectedUnit = filters.unit;
    const listPriceMin = Number(filters.listPrice.min);
    const listPriceMax = Number(filters.listPrice.max);
    const distributorCostMin = Number(filters.distributorCost.min);
    const distributorCostMax = Number(filters.distributorCost.max);

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
      const hasWarehouse = Boolean((item.warehouse || item.warehouse_location || item.location || "").trim());
      const warehouseMatches = !filters.warehouseOnly || hasWarehouse;
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

  const dashboardStats = [
    { label: "Catalog SKUs under review", value: "12,481", trend: "+4.2% this week" },
    { label: "Rows with margin risk", value: "318", trend: "-1.8% vs last run" },
    { label: "Price updates published", value: "96", trend: "+12 today" },
    { label: "Connectors healthy", value: "4 / 4", trend: "No outages in 24h" }
  ];

  return (
    <div className="page">
      <div className="container">
        <nav className="menu-bar">
          <div className="menu-title">QuoteSense Internal Console</div>
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
              <aside className="filter-sidebar panel">
                <h2>Filters</h2>
                <p className="panel-subtext">Structured filtering for catalog management and pricing governance.</p>

                <div className="search-box search-box-compact">
                  <input
                    value={query}
                    onChange={(e) => handleQueryChange(e.target.value)}
                    placeholder="Search SCN pricing table by model, manufacturer, description, or part number"
                  />
                </div>

                <label className="filter-group">
                  <span>Model</span>
                  <input value={filters.model} onChange={(e) => updateFilter("model", e.target.value)} placeholder="Filter model" />
                </label>

                <label className="filter-group">
                  <span>Manufacturer Model</span>
                  <input
                    value={filters.manufacturerModel}
                    onChange={(e) => updateFilter("manufacturerModel", e.target.value)}
                    placeholder="Filter manufacturer model"
                  />
                </label>

                <div className="filter-group">
                  <span>List Price Range</span>
                  <div className="range-row">
                    <input
                      type="number"
                      value={filters.listPrice.min}
                      onChange={(e) => updateRangeFilter("listPrice", "min", e.target.value)}
                      placeholder="Min"
                    />
                    <input
                      type="number"
                      value={filters.listPrice.max}
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
                      value={filters.distributorCost.min}
                      onChange={(e) => updateRangeFilter("distributorCost", "min", e.target.value)}
                      placeholder="Min"
                    />
                    <input
                      type="number"
                      value={filters.distributorCost.max}
                      onChange={(e) => updateRangeFilter("distributorCost", "max", e.target.value)}
                      placeholder="Max"
                    />
                  </div>
                </div>

                <label className="filter-group checkbox-row">
                  <input
                    type="checkbox"
                    checked={filters.warehouseOnly}
                    onChange={(e) => updateFilter("warehouseOnly", e.target.checked)}
                  />
                  <span>Warehouse records only</span>
                </label>

                <label className="filter-group">
                  <span>Unit</span>
                  <select value={filters.unit} onChange={(e) => updateFilter("unit", e.target.value)}>
                    {unitOptions.map((option) => (
                      <option key={option} value={option}>{option === "all" ? "All units" : option}</option>
                    ))}
                  </select>
                </label>
              </aside>

              <div className="pricing-content">
                {!canSearch && (
                  <div className="info-box muted-box">Type a search term to load results.</div>
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
      </div>
    </div>
  );
}

export default App;
