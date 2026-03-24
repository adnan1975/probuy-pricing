import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const expectedSources = ["SCN Pricing", "White Cap", "KMS Tools", "Canadian Tire", "Home Depot"];

const fallbackExamples = [
  {
    id: "all-scn",
    label: "All SCN catalog items",
    query: ""
  },
  {
    id: "grinder",
    label: "DEWALT FLEXVOLT grinder DCG418B",
    query: "DEWALT FLEXVOLT grinder DCG418B"
  },
  {
    id: "glasses",
    label: "3M SecureFit SF201AF safety glasses",
    query: "3M SecureFit SF201AF safety glasses"
  }
];

function App() {
  const [catalogItems, setCatalogItems] = useState([]);
  const [selectedExampleId, setSelectedExampleId] = useState("all-scn");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [perSourceErrors, setPerSourceErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadCatalogItems() {
      try {
        const res = await fetch(`${API_URL}/catalog/items?limit=250`, {
          signal: controller.signal
        });
        if (!res.ok) {
          throw new Error(`Catalog request returned ${res.status}`);
        }
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setCatalogItems(data);
        } else {
          setCatalogItems(fallbackExamples.map((item) => item.query).filter(Boolean));
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          setCatalogItems(fallbackExamples.map((item) => item.query).filter(Boolean));
        }
      }
    }

    loadCatalogItems();
    return () => controller.abort();
  }, []);

  const examples = useMemo(() => {
    const options = [fallbackExamples[0]];
    const unique = new Set();

    for (const item of catalogItems) {
      const normalized = (item || "").trim();
      if (!normalized) {
        continue;
      }
      const key = normalized.toLowerCase();
      if (unique.has(key)) {
        continue;
      }
      unique.add(key);
      options.push({
        id: `catalog-${key}`,
        label: normalized,
        query: normalized
      });
      if (options.length >= 51) {
        break;
      }
    }

    if (options.length < 3) {
      options.push(...fallbackExamples.slice(1));
    }

    return options;
  }, [catalogItems]);

  useEffect(() => {
    const selectedExample = examples.find((item) => item.id === selectedExampleId);
    if (selectedExample) {
      setQuery(selectedExample.query);
    }
  }, [selectedExampleId, examples]);

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
      } catch (err) {
        if (err.name !== "AbortError") {
          setApiError(err.message || "Could not load results");
          setResults([]);
          setAnalysis(null);
          setPerSourceErrors({});
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

  const bestResult = useMemo(() => {
    return results.find((item) => typeof item.price_value === "number") || null;
  }, [results]);

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
            list="catalog-suggestions"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by model, description, brand, or part number"
          />
          <datalist id="catalog-suggestions">
            {catalogItems.slice(0, 100).map((item) => (
              <option key={item} value={item} />
            ))}
          </datalist>
          <select value={selectedExampleId} onChange={(e) => setSelectedExampleId(e.target.value)}>
            {examples.map((example) => (
              <option key={example.id} value={example.id}>
                {example.label}
              </option>
            ))}
          </select>
        </div>

        <div className="summary-grid">
          <div className="summary-card"><div className="label">Search term</div><div className="value">{query || "(all items)"}</div></div>
          <div className="summary-card"><div className="label">Configured sources</div><div className="value">{expectedSources.length}</div></div>
          <div className="summary-card"><div className="label">Catalog suggestions</div><div className="value">{catalogItems.length}</div></div>
          <div className="summary-card"><div className="label">Priced results</div><div className="value">{analysis?.priced_results ?? 0}</div></div>
        </div>

        <div className="panel">
          <h2>Normalized connector results</h2>
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
                </tr>
              </thead>
              <tbody>
                {results.map((item, idx) => (
                  <tr key={`${item.source}-${idx}`}>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <h2>Analysis</h2>
          <div className="summary-grid two-cols compact-grid">
            <div className="summary-card"><div className="label">Lowest</div><div className="value">{analysis?.lowest_price != null ? `$${analysis.lowest_price.toFixed(2)}` : "$--"}</div></div>
            <div className="summary-card"><div className="label">Highest</div><div className="value">{analysis?.highest_price != null ? `$${analysis.highest_price.toFixed(2)}` : "$--"}</div></div>
            <div className="summary-card"><div className="label">Average</div><div className="value">{analysis?.average_price != null ? `$${analysis.average_price.toFixed(2)}` : "$--"}</div></div>
            <div className="summary-card"><div className="label">Source errors</div><div className="value">{Object.keys(perSourceErrors).length}</div></div>
          </div>
          {Object.keys(perSourceErrors).length > 0 && (
            <div className="info-box">
              {Object.entries(perSourceErrors).map(([source, error]) => (
                <div key={source}><strong>{source}:</strong> {error}</div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <h2>Quote guidance</h2>
          {bestResult ? (
            <div className="recommend-box">
              Recommended baseline: <strong>{bestResult.source}</strong> at{" "}
              <strong>{bestResult.price_text || `$${bestResult.price_value?.toFixed(2)}`}</strong>.
              {bestResult.why ? ` Reason: ${bestResult.why}` : ""}
            </div>
          ) : (
            <div className="info-box">No priced results yet; quote guidance will appear when pricing is available.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
