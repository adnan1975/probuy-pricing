import { Fragment, useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const expectedSources = ["SCN Pricing", "White Cap", "KMS Tools", "Canadian Tire", "Home Depot", "Amazon.ca"];
const PAGE_SIZE_OPTIONS = [10, 25, 50];
const MIN_QUERY_LENGTH = 4;

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [perSourceErrors, setPerSourceErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [step2Loading, setStep2Loading] = useState(false);
  const [apiError, setApiError] = useState("");

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(0);
  const [totalResults, setTotalResults] = useState(0);
  const [expandedRows, setExpandedRows] = useState({});

  const trimmedQuery = query.trim();
  const canSearch = trimmedQuery.length >= MIN_QUERY_LENGTH;

  useEffect(() => {
    const controller = new AbortController();

    async function loadResults() {
      if (!canSearch) {
        setLoading(false);
        setStep2Loading(false);
        setApiError("");
        setResults([]);
        setAnalysis(null);
        setPerSourceErrors({});
        setTotalPages(0);
        setTotalResults(0);
        return;
      }

      setLoading(true);
      setApiError("");
      try {
        const step1Params = new URLSearchParams({
          product: trimmedQuery,
          page: String(page),
          page_size: String(pageSize)
        });
        const step1Res = await fetch(`${API_URL}/search/step1?${step1Params.toString()}`, {
          signal: controller.signal
        });
        if (!step1Res.ok) {
          throw new Error(`Backend returned ${step1Res.status} from step1`);
        }
        const step1Data = await step1Res.json();
        const scnResults = Array.isArray(step1Data.results) ? step1Data.results : [];
        setResults(scnResults);
        setAnalysis(step1Data.analysis || null);
        setPerSourceErrors(step1Data.per_source_errors || {});
        setTotalPages(step1Data.total_pages || 0);
        setTotalResults(step1Data.total_results || 0);

        if (scnResults.length === 0) {
          setStep2Loading(false);
          return;
        }

        setStep2Loading(true);
        const step2Params = new URLSearchParams({ product: trimmedQuery });
        const step2Res = await fetch(`${API_URL}/search/step2?${step2Params.toString()}`, {
          signal: controller.signal
        });
        if (!step2Res.ok) {
          throw new Error(`Backend returned ${step2Res.status} from step2`);
        }
        const step2Data = await step2Res.json();
        const step2Results = Array.isArray(step2Data.results) ? step2Data.results : [];
        setResults([...scnResults, ...step2Results]);
        setPerSourceErrors({
          ...(step1Data.per_source_errors || {}),
          ...(step2Data.per_source_errors || {})
        });
        setAnalysis({
          ...(step1Data.analysis || {}),
          total_results: scnResults.length + step2Results.length,
          priced_results: [...scnResults, ...step2Results].filter((item) => typeof item.price_value === "number").length
        });
        setTotalResults(scnResults.length + step2Results.length);
      } catch (err) {
        if (err.name !== "AbortError") {
          setApiError(err.message || "Could not load results");
          setResults([]);
          setAnalysis(null);
          setPerSourceErrors({});
          setTotalPages(0);
          setTotalResults(0);
        }
      } finally {
        setStep2Loading(false);
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

  const scnPrimaryResults = useMemo(
    () => results.filter((item) => item.source === "SCN Pricing"),
    [results]
  );

  const visibleResults = scnPrimaryResults;

  const relatedOffersByRow = useMemo(() => {
    const nonScnResults = results.filter((item) => item.source !== "SCN Pricing");

    function tokenize(value) {
      return String(value || "")
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter((token) => token.length >= 4);
    }

    return visibleResults.reduce((acc, primary, idx) => {
      const keys = new Set([
        String(primary.sku || "").toLowerCase(),
        String(primary.manufacturer_model || "").toLowerCase()
      ].filter(Boolean));

      tokenize(primary.title).forEach((token) => keys.add(token));

      const offers = nonScnResults.filter((offer) => {
        const candidate = [offer.sku, offer.manufacturer_model, offer.title]
          .map((entry) => String(entry || "").toLowerCase())
          .join(" ");

        for (const key of keys) {
          if (key && candidate.includes(key)) {
            return true;
          }
        }
        return false;
      });

      // Supabase can contain historical snapshots. Keep one row (latest) per connector source in details.
      const latestBySource = new Map();
      offers.forEach((offer) => {
        const sourceKey = String(offer.source || "").toLowerCase();
        if (!latestBySource.has(sourceKey)) {
          latestBySource.set(sourceKey, offer);
        }
      });

      acc[idx] = Array.from(latestBySource.values());
      return acc;
    }, {});
  }, [results, visibleResults]);

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

  function handleQueryChange(value) {
    setQuery(value);
    setPage(1);
    setExpandedRows({});
  }

  function handlePageSizeChange(value) {
    setPageSize(Number(value));
    setPage(1);
    setExpandedRows({});
  }

  function toggleDetails(index) {
    setExpandedRows((prev) => ({ ...prev, [index]: !prev[index] }));
  }

  return (
    <div className="page">
      <div className="container">
        <div className="topbar">
          <div>
            <div className="tag">QuoteSense Pricing Console</div>
            <h1>SCN Primary Price Discovery</h1>
            <p>Showing SCN-matched catalog results first. If no SCN match is found, no results are displayed.</p>
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
          {loading && <div className="info-box">Loading SCN pricing...</div>}
          {!loading && step2Loading && <div className="info-box">SCN pricing loaded. Fetching retailer details...</div>}
          {!loading && !apiError && canSearch && visibleResults.length === 0 && <div className="info-box">No SCN matches were found for this query.</div>}
          {!loading && !apiError && canSearch && visibleResults.length > 0 && (analysis?.priced_results ?? 0) === 0 && (
            <div className="info-box">No price could be found yet. Items are shown with defaults so you can still compare sources.</div>
          )}

          <div className="pagination-controls">
            <div>
              Showing <strong>{visibleResults.length}</strong> of <strong>{totalResults}</strong> results
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
                  <th>Warehouse Location</th>
                  <th>Price</th>
                  <th>Availability</th>
                  <th>Suggested Price</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleResults.map((item, idx) => {
                  const rowKey = `${item.source}-${idx}`;
                  const relatedOffers = relatedOffersByRow[idx] || [];
                  const isExpanded = Boolean(expandedRows[idx]);
                  return (
                    <Fragment key={rowKey}>
                      <tr>
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
                        <td>{item.location || item.warehouse_location || item.warehouse || "N/A"}</td>
                        <td>{item.price_text || "Price unavailable"}</td>
                        <td>{item.availability || "Unknown"}</td>
                        <td className="suggested-price">{formatSuggestedPrice(item, idx)}</td>
                        <td>
                          <button className="publish-btn" type="button">
                            Publish Price
                          </button>
                          {step2Loading ? (
                            <span className="details-loader" aria-live="polite">Loading details...</span>
                          ) : (
                            <button
                              className="details-btn"
                              type="button"
                              onClick={() => toggleDetails(idx)}
                              disabled={relatedOffers.length === 0}
                            >
                              {isExpanded ? "Hide Details" : "Show Details"}
                            </button>
                          )}
                        </td>
                      </tr>
                      {isExpanded && relatedOffers.length > 0 && (
                        <tr className="details-row">
                          <td colSpan={9}>
                            <div className="details-title">Connector prices for {item.sku || item.title}</div>
                            <div className="details-grid">
                              {relatedOffers.map((offer, offerIndex) => (
                                <div className="details-card" key={`${offer.source}-${offerIndex}`}>
                                  <div className="table-strong">{offer.source}</div>
                                  <div>{offer.price_text || "Price unavailable"}</div>
                                  <div className="table-sub">{offer.availability || "Unknown"}</div>
                                </div>
                              ))}
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
