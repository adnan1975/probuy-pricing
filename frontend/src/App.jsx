import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const expectedSources = ["SCN Pricing", "White Cap", "KMS Tools", "Canadian Tire", "Home Depot"];

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [perSourceErrors, setPerSourceErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  const [expandedRowKey, setExpandedRowKey] = useState(null);
  const [expandedLoading, setExpandedLoading] = useState(false);
  const [expandedError, setExpandedError] = useState("");
  const [expandedAnalysis, setExpandedAnalysis] = useState(null);
  const [expandedPerSourceErrors, setExpandedPerSourceErrors] = useState({});
  const [expandedSourcePrices, setExpandedSourcePrices] = useState([]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadResults() {
      setLoading(true);
      setApiError("");
      try {
        const res = await fetch(`${API_URL}/search?product=${encodeURIComponent(query)}`, {
          signal: controller.signal
        });
        if (!res.ok) {
          throw new Error(`Backend returned ${res.status}`);
        }
        const data = await res.json();
        setResults(Array.isArray(data.results) ? data.results : []);
        setAnalysis(data.analysis || null);
        setPerSourceErrors(data.per_source_errors || {});
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
  }, [query]);

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
      const res = await fetch(`${API_URL}/search?product=${encodeURIComponent(lookupQuery)}`);
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

  return (
    <div className="page">
      <div className="container">
        <div className="topbar">
          <div>
            <div className="tag">QuoteSense Pricing Console</div>
            <h1>Connector-based retailer + SCN price discovery</h1>
            <p>Live retailer/distributor connectors plus Supabase-backed SCN pricing catalog.</p>
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
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by model, description, brand, or part number"
          />
        </div>

        <div className="summary-grid">
          <div className="summary-card"><div className="label">Search term</div><div className="value">{query || "(all items)"}</div></div>
          <div className="summary-card"><div className="label">Configured sources</div><div className="value">{expectedSources.length}</div></div>
          <div className="summary-card"><div className="label">Total results</div><div className="value">{analysis?.total_results ?? 0}</div></div>
          <div className="summary-card"><div className="label">Priced results</div><div className="value">{analysis?.priced_results ?? 0}</div></div>
        </div>

        <div className="panel">
          <h2>Items found</h2>
          {apiError && <div className="error-box"><strong>API error:</strong> {apiError}</div>}
          {loading && <div className="info-box">Loading connector results...</div>}
          {!loading && !apiError && results.length === 0 && <div className="info-box">No matches were found for this query.</div>}
          {!loading && !apiError && results.length > 0 && (analysis?.priced_results ?? 0) === 0 && (
            <div className="info-box">No price could be found yet. Items are shown with defaults so you can still compare sources.</div>
          )}

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
                    <tr key={rowKey} className={isExpanded ? "expanded-row" : ""}>
                      <td>{idx + 1}</td>
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
                  );
                })}
              </tbody>
            </table>
          </div>

          {expandedRowKey && (
            <div className="expanded-panel">
              <h3>Analysis & quote guidance (expanded item)</h3>
              {expandedError && <div className="error-box"><strong>API error:</strong> {expandedError}</div>}
              {expandedLoading && <div className="info-box">Checking all connectors for pricing...</div>}

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
                        {expandedSourcePrices.map((item) => (
                          <tr key={`expanded-${item.source}`}>
                            <td>{item.source}</td>
                            <td>{item.price_text}</td>
                            <td>{item.why}</td>
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
          )}

          {!expandedRowKey && !loading && !apiError && (
            <div className="info-box muted-box">Expand one item to view its analysis and quote guidance.</div>
          )}
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
