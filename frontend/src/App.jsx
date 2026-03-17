import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const examples = [
  {
    id: "grinder",
    label: "DEWALT FlexVolt Grinder",
    customer: "West Coast Marine",
    query: "Price Flexvolt Perform & Protect Max Brushless Cordless Grinder",
    brand: "DEWALT",
    partNumber: "DCG418B",
    category: "Power Tools / Grinders"
  },
  {
    id: "glasses",
    label: "3M SecureFit Glasses",
    customer: "West Coast Marine",
    query: "3M SecureFit SF201AF clear anti-fog glasses",
    brand: "3M",
    partNumber: "SF201AF",
    category: "PPE / Safety Eyewear"
  }
];

function App() {
  const [selectedExampleId, setSelectedExampleId] = useState("grinder");
  const [results, setResults] = useState([]);
  const [sourceLabels, setSourceLabels] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  const selected = useMemo(
    () => examples.find((item) => item.id === selectedExampleId) || examples[0],
    [selectedExampleId]
  );

  useEffect(() => {
    const controller = new AbortController();

    async function loadResults() {
      setLoading(true);
      setApiError("");
      try {
        const res = await fetch(`${API_URL}/search?product=${encodeURIComponent(selected.query)}`, {
          signal: controller.signal
        });
        if (!res.ok) {
          throw new Error(`Backend returned ${res.status}`);
        }
        const data = await res.json();
        setResults(Array.isArray(data.results) ? data.results : []);
        setSourceLabels(Array.isArray(data.source_labels) ? data.source_labels : []);
        setAnalysis(data.analysis || null);
      } catch (err) {
        if (err.name !== "AbortError") {
          setApiError(err.message || "Could not load results");
          setResults([]);
          setSourceLabels([]);
          setAnalysis(null);
        }
      } finally {
        setLoading(false);
      }
    }

    loadResults();
    return () => controller.abort();
  }, [selected.query]);

  return (
    <div className="page">
      <div className="container">
        <div className="topbar">
          <div>
            <div className="tag">QuoteSense Pricing Console</div>
            <h1>Connector-based retailer price discovery</h1>
            <p>Search results are aggregated from direct retailer connectors (no SERP dependency).</p>
          </div>

          <div className="help-card">
            <div className="help-title">Sources</div>
            <div>{sourceLabels.join(", ") || "No sources loaded"}</div>
          </div>
        </div>

        <div className="search-box">
          <input value={selected.query} readOnly />
          <select value={selectedExampleId} onChange={(e) => setSelectedExampleId(e.target.value)}>
            {examples.map((example) => (
              <option key={example.id} value={example.id}>
                {example.label}
              </option>
            ))}
          </select>
        </div>

        <div className="summary-grid">
          <div className="summary-card"><div className="label">Customer</div><div className="value">{selected.customer}</div></div>
          <div className="summary-card"><div className="label">Brand</div><div className="value">{selected.brand}</div></div>
          <div className="summary-card"><div className="label">Part Number</div><div className="value">{selected.partNumber}</div></div>
          <div className="summary-card"><div className="label">Category</div><div className="value">{selected.category}</div></div>
          <div className="summary-card"><div className="label">Source count</div><div className="value">{analysis?.source_count ?? 0}</div></div>
          <div className="summary-card"><div className="label">Results</div><div className="value">{loading ? "Loading..." : results.length}</div></div>
        </div>

        <div className="panel">
          <h2>Normalized connector results</h2>
          {apiError && <div className="error-box"><strong>API error:</strong> {apiError}</div>}
          {loading && <div className="info-box">Loading connector results...</div>}
          {!loading && !apiError && results.length === 0 && <div className="info-box">No results returned.</div>}

          <div className="serp-table-wrap">
            <table className="serp-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Source</th>
                  <th>Title</th>
                  <th>SKU</th>
                  <th>Price</th>
                  <th>Stock</th>
                </tr>
              </thead>
              <tbody>
                {results.map((item, idx) => (
                  <tr key={`${item.source}-${idx}`}>
                    <td>{idx + 1}</td>
                    <td>
                      <div className="table-strong">{item.source_label}</div>
                      <div className="table-sub">{item.source}</div>
                    </td>
                    <td>{item.title}</td>
                    <td>{item.sku || "N/A"}</td>
                    <td>{item.price}</td>
                    <td>{item.stock || "Unknown"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <h2>Analysis</h2>
          <div className="summary-grid two-cols compact-grid">
            <div className="summary-card"><div className="label">Lowest</div><div className="value">{analysis?.lowest != null ? `$${analysis.lowest.toFixed(2)}` : "$--"}</div></div>
            <div className="summary-card"><div className="label">Highest</div><div className="value">{analysis?.highest != null ? `$${analysis.highest.toFixed(2)}` : "$--"}</div></div>
            <div className="summary-card"><div className="label">Average</div><div className="value">{analysis?.average != null ? `$${analysis.average.toFixed(2)}` : "$--"}</div></div>
            <div className="summary-card"><div className="label">Sources in result</div><div className="value">{analysis?.source_count ?? 0}</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
