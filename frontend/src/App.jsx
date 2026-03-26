import { Fragment, useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const expectedSources = ["SCN Pricing", "White Cap", "KMS Tools", "Canadian Tire", "Home Depot"];
const PAGE_SIZE_OPTIONS = [10, 25, 50];
const MIN_QUERY_LENGTH = 4;

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [perSourceErrors, setPerSourceErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(0);
  const [totalResults, setTotalResults] = useState(0);

  const [expandedRowKey, setExpandedRowKey] = useState(null);
  const [expandedLoading, setExpandedLoading] = useState(false);
  const [expandedError, setExpandedError] = useState("");
  const [expandedAnalysis, setExpandedAnalysis] = useState(null);
  const [expandedPerSourceErrors, setExpandedPerSourceErrors] = useState({});
  const [expandedSourcePrices, setExpandedSourcePrices] = useState([]);

  const trimmedQuery = query.trim();
  const canSearch = trimmedQuery.length >= MIN_QUERY_LENGTH;

  useEffect(() => {
    const controller = new AbortController();

    async function loadResults() {
      if (!canSearch) {
        setLoading(false);
        setApiError("");
        setResults([]);
        setAnalysis(null);
        setPerSourceErrors({});
        setTotalPages(0);
        setTotalResults(0);
        setExpandedRowKey(null);
        return;
      }

      setLoading(true);
      setApiError("");
      try {
        const params = new URLSearchParams({
          product: trimmedQuery,
          page: String(page),
          page_size: String(pageSize)
        });
        const res = await fetch(`${API_URL}/search?${params.toString()}`, {
          signal: controller.signal
        });
        if (!res.ok) {
          throw new Error(`Backend returned ${res.status}`);
        }
        const data = await res.json();
        setResults(Array.isArray(data.results) ? data.results : []);
        setAnalysis(data.analysis || null);
        setPerSourceErrors(data.per_source_errors || {});
        setTotalPages(data.total_pages || 0);
        setTotalResults(data.total_results || 0);
        setExpandedRowKey(null);
        setExpandedLoading(false);
        setExpandedError("");
        setExpandedAnalysis(null);
        setExpandedPerSourceErrors({});
        setExpandedSourcePrices([]);
      } catch (err) {
        if (err.name !== "AbortError") {
          setApiError(err.message || "Could not load results");
          setResults([]);
          setAnalysis(null);
          setPerSourceErrors({});
          setTotalPages(0);
          setTotalResults(0);
          setExpandedRowKey(null);
          setExpandedLoading(false);
          setExpandedError("");
          setExpandedAnalysis(null);
          setExpandedPerSourceErrors({});
          setExpandedSourcePrices([]);
        }
      } finally {
        setLoading(false);
      }
    }

    loadResults();
    return () => controller.abort();
  }, [canSearch, page, pageSize, trimmedQuery]);

  const sourceSummary = useMemo(() => {
    const inResults = new Set(results.map((item) => item.source).filter(Boolean));
    return expectedSources.map((source) => ({
      source,
      inResults: inResults.has(source)
    }));
  }, [results]);

  const expandedBestResult = useMemo(() => {
    return expandedSourcePrices.find((item) => typeof item.price_value === "number") || null;
  }, [expandedSourcePrices]);

  async function handleToggleExpand(item, idx) {
    const rowKey = `${item.source}-${idx}`;
    if (expandedRowKey === rowKey) {
      setExpandedRowKey(null);
      setExpandedLoading(false);
      setExpandedError("");
      setExpandedAnalysis(null);
      setExpandedPerSourceErrors({});
      setExpandedSourcePrices([]);
      return;
    }

    setExpandedRowKey(rowKey);
    setExpandedLoading(true);
    setExpandedError("");
    setExpandedAnalysis(null);
    setExpandedPerSourceErrors({});
    setExpandedSourcePrices([]);

    try {
      const lookupQuery = item.sku?.trim() || item.title?.trim() || item.product_url?.trim() || "";
      const params = new URLSearchParams({
        product: lookupQuery,
        page: "1",
        page_size: "100"
      });
      const res = await fetch(`${API_URL}/search?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`Backend returned ${res.status}`);
      }
      const data = await res.json();
      const lookupResults = Array.isArray(data.results) ? data.results : [];
      const sourceList = Array.from(new Set([...expectedSources, ...lookupResults.map((r) => r.source).filter(Boolean)]));

      const pricesBySource = sourceList.map((source) => {
        const bySource = lookupResults.filter((result) => result.source === source);
        const pricedMatch = bySource.find((result) => typeof result.price_value === "number") || bySource[0] || null;
        return {
          source,
          source_type: pricedMatch?.source_type || "retail",
          price_text: pricedMatch?.price_text || "Price unavailable",
          price_value: pricedMatch?.price_value,
          why: pricedMatch?.why || "No explanation provided"
        };
      });

      setExpandedSourcePrices(pricesBySource);
      setExpandedAnalysis(data.analysis || null);
      setExpandedPerSourceErrors(data.per_source_errors || {});
    } catch (err) {
      setExpandedError(err.message || "Could not load source pricing for this item");
    } finally {
      setExpandedLoading(false);
    }
  }

  function handleQueryChange(value) {
    setQuery(value);
    setPage(1);
  }

  function handlePageSizeChange(value) {
    setPageSize(Number(value));
    setPage(1);
  }

  return (
    <div className="page">
      <div className="container">
        <div className="topbar">
          <div>
            <div className="tag">QuoteSense Pricing Console</div>
            <h1>Connector-based retailer + SCN price discovery</h1>
            <p>Supabase-backed connector price history plus SCN pricing catalog.</p>
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

        <div className="panel">
          <h2>Items found</h2>
          {apiError && <div className="error-box"><strong>API error:</strong> {apiError}</div>}
          {loading && <div className="info-box">Loading connector results from Supabase...</div>}
          {!loading && !apiError && canSearch && results.length === 0 && <div className="info-box">No matches were found for this query.</div>}
          {!loading && !apiError && canSearch && results.length > 0 && (analysis?.priced_results ?? 0) === 0 && (
            <div className="info-box">No price could be found yet. Items are shown with defaults so you can still compare sources.</div>
          )}

          <div className="pagination-controls">
            <div>
              Showing <strong>{results.length}</strong> of <strong>{totalResults}</strong> results
            </div>
            <label>
              Page size
              <select value={pageSize} onChange={(e) => handlePageSizeChange(e.target.value)}>
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
            </label>
            <div className="page-buttons">
              <button onClick={() => setPage((prev) => Math.max(1, prev - 1))} disabled={!canSearch || loading || page <= 1}>
                Previous
              </button>
              <span>Page {totalPages === 0 ? 0 : page} of {totalPages}</span>
              <button
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={!canSearch || loading || totalPages === 0 || page >= totalPages}
              >
                Next
              </button>
            </div>
          </div>

          <div className="retailer-table-wrap">
            <table className="retailer-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Source</th>
                  <th>Title</th>
                  <th>SKU</th>
                  <th>Price</th>
                  <th>Availability</th>
                  <th>Why ranked</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {results.map((item, idx) => {
                  const rowKey = `${item.source}-${idx}`;
                  const isExpanded = expandedRowKey === rowKey;

                  return (
                    <Fragment key={rowKey}>
                      <tr className={isExpanded ? "expanded-row" : ""}>
                        <td>{(page - 1) * pageSize + idx + 1}</td>
                        <td>
                          <div className="table-strong">{item.source}</div>
                          <div className="table-sub">
                            <span className={`pill ${item.source_type === "distributor" ? "green" : "blue"}`}>
                              {item.source_type || "retail"}
                            </span>
                          </div>
                        </td>
                        <td>{item.title}</td>
                        <td>{item.sku || "N/A"}</td>
                        <td>{item.price_text || "Price unavailable"}</td>
                        <td>{item.availability || "Unknown"}</td>
                        <td>{item.why || "No explanation provided"}</td>
                        <td>
                          <button className="expand-link" onClick={() => handleToggleExpand(item, idx)}>
                            {isExpanded ? "Collapse" : "Expand"}
                          </button>
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="accordion-row">
                          <td colSpan={8}>
                            <div className="expanded-panel in-table">
                              <h3>Analysis & quote guidance (expanded item)</h3>
                              {expandedError && <div className="error-box"><strong>API error:</strong> {expandedError}</div>}
                              {expandedLoading && <div className="info-box">Loading source pricing snapshot from Supabase...</div>}

                              {!expandedLoading && !expandedError && (
                                <>
                                  <div className="summary-grid two-cols compact-grid">
                                    <div className="summary-card"><div className="label">Lowest</div><div className="value">{expandedAnalysis?.lowest_price != null ? `$${expandedAnalysis.lowest_price.toFixed(2)}` : "$--"}</div></div>
                                    <div className="summary-card"><div className="label">Highest</div><div className="value">{expandedAnalysis?.highest_price != null ? `$${expandedAnalysis.highest_price.toFixed(2)}` : "$--"}</div></div>
                                    <div className="summary-card"><div className="label">Average</div><div className="value">{expandedAnalysis?.average_price != null ? `$${expandedAnalysis.average_price.toFixed(2)}` : "$--"}</div></div>
                                    <div className="summary-card"><div className="label">Source errors</div><div className="value">{Object.keys(expandedPerSourceErrors).length}</div></div>
                                  </div>

                                  <div className="retailer-table-wrap">
                                    <table className="retailer-table compact-table">
                                      <thead>
                                        <tr>
                                          <th>Source</th>
                                          <th>Price check</th>
                                          <th>Why ranked</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {expandedSourcePrices.map((expandedItem) => (
                                          <tr key={`expanded-${expandedItem.source}`}>
                                            <td>{expandedItem.source}</td>
                                            <td>{expandedItem.price_text}</td>
                                            <td>{expandedItem.why}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>

                                  {Object.keys(expandedPerSourceErrors).length > 0 && (
                                    <div className="info-box">
                                      {Object.entries(expandedPerSourceErrors).map(([source, error]) => (
                                        <div key={source}><strong>{source}:</strong> {error}</div>
                                      ))}
                                    </div>
                                  )}

                                  {expandedBestResult ? (
                                    <div className="recommend-box">
                                      Recommended baseline: <strong>{expandedBestResult.source}</strong> at{" "}
                                      <strong>{expandedBestResult.price_text || `$${expandedBestResult.price_value?.toFixed(2)}`}</strong>.
                                      {expandedBestResult.why ? ` Reason: ${expandedBestResult.why}` : ""}
                                    </div>
                                  ) : (
                                    <div className="info-box">No priced results yet; quote guidance will appear when pricing is available.</div>
                                  )}
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

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
