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
    category: "Power Tools / Grinders",
    summary:
      "This example shows preferred supplier pricing against all live SERP and shopping results with market analysis.",
    selectedSource: "SCN Industrial",
    selectedCost: "$329.00",
    targetMargin: "18%",
    suggestedSellPrice: "$401.38"
  },
  {
    id: "glasses",
    label: "3M SecureFit Glasses",
    customer: "West Coast Marine",
    query: "3M SecureFit SF201AF clear anti-fog glasses",
    brand: "3M",
    partNumber: "SF201AF",
    category: "PPE / Safety Eyewear",
    summary:
      "This example shows exact supplier pricing with Google organic and shopping results used as market intelligence.",
    selectedSource: "SCN Industrial",
    selectedCost: "$13.10",
    targetMargin: "32%",
    suggestedSellPrice: "$19.25"
  }
];

function App() {
  const [selectedExampleId, setSelectedExampleId] = useState("grinder");
  const [preferredResults, setPreferredResults] = useState([]);
  const [serpResults, setSerpResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [serpError, setSerpError] = useState("");
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
      setSerpError("");

      try {
        const res = await fetch(
          `${API_URL}/search?product=${encodeURIComponent(selected.query)}`,
          { signal: controller.signal }
        );

        if (!res.ok) {
          throw new Error(`Backend returned ${res.status}`);
        }

        const data = await res.json();
        setPreferredResults(Array.isArray(data.preferredResults) ? data.preferredResults : []);
        setSerpResults(Array.isArray(data.serpResults) ? data.serpResults : []);
        setAnalysis(data.analysis || null);
        setSerpError(data.serpError || "");
      } catch (err) {
        if (err.name !== "AbortError") {
          console.error("API error:", err);
          setApiError(err.message || "Could not load results");
          setPreferredResults([]);
          setSerpResults([]);
          setAnalysis(null);
        }
      } finally {
        setLoading(false);
      }
    }

    loadResults();

    return () => controller.abort();
  }, [selected.query]);

  const toneClasses = {
    preferred: "pill-source preferred",
    google: "pill-source google",
    competitor: "pill-source competitor",
    review: "pill-source review"
  };

  const scorePill = (score) => {
    if (score >= 90) return "pill green";
    if (score >= 80) return "pill amber";
    return "pill red";
  };

  const confidencePill = (confidence) => {
    if (confidence === "High") return "pill blue";
    if (confidence === "Medium") return "pill orange";
    return "pill gray";
  };

  return (
    <div className="page">
      <div className="container">
        <div className="topbar">
          <div>
            <div className="tag">ProBuy Pricing Console</div>
            <h1>AI-assisted sourcing and pricing search</h1>
            <p>
              Show every live SERP result, separate trusted supplier pricing from market discovery,
              and explain the price range clearly before quoting.
            </p>
          </div>

          <div className="help-card">
            <div className="help-title">How to read this screen</div>
            <div>
              Green = trusted supplier feed, blue = Google result. Supplier pricing is for quoting.
              SERP results are for market awareness and validation.
            </div>
          </div>
        </div>

        <div className="search-box">
          <input value={selected.query} readOnly />
          <select
            value={selectedExampleId}
            onChange={(e) => setSelectedExampleId(e.target.value)}
          >
            {examples.map((example) => (
              <option key={example.id} value={example.id}>
                {example.label}
              </option>
            ))}
          </select>
        </div>

        <div className="demo-note">
          <strong>Demo explanation:</strong> {selected.summary}
        </div>

        <div className="summary-grid">
          <div className="summary-card">
            <div className="label">Customer</div>
            <div className="value">{selected.customer}</div>
          </div>
          <div className="summary-card">
            <div className="label">Brand</div>
            <div className="value">{selected.brand}</div>
          </div>
          <div className="summary-card">
            <div className="label">Part Number</div>
            <div className="value">{selected.partNumber}</div>
          </div>
          <div className="summary-card">
            <div className="label">Category</div>
            <div className="value">{selected.category}</div>
          </div>
          <div className="summary-card">
            <div className="label">Preferred results</div>
            <div className="value">{preferredResults.length}</div>
          </div>
          <div className="summary-card">
            <div className="label">SERP results</div>
            <div className="value">{loading ? "Loading..." : serpResults.length}</div>
          </div>
        </div>

        <div className="main-grid">
          <div className="left-column">
            <div className="panel">
              <h2>Preferred supplier pricing</h2>
              <p className="panel-subtext">
                These are your trusted operational sources and should be treated as the primary quote candidates.
              </p>

              {preferredResults.map((item, idx) => (
                <div className="result-row" key={`preferred-${idx}`}>
                  <div className="result-main">
                    <div className="result-top">
                      <span className="vendor-name">{item.vendor}</span>
                      <span className="pill-source preferred">{item.source}</span>
                      <span className={scorePill(item.score || 0)}>Score {item.score ?? "--"}</span>
                      <span className={confidencePill(item.confidence || "Low")}>
                        {item.confidence || "Low"} confidence
                      </span>
                    </div>

                    <div className="title">{item.title}</div>

                    <div className="detail-grid">
                      <div>MPN / SKU: {item.sku || "N/A"}</div>
                      <div>Availability: {item.stock || "Unknown"}</div>
                      <div>Freshness: {item.freshness || "Unknown"}</div>
                      <div>Source note: {item.sourceNote || "N/A"}</div>
                    </div>

                    <div className="why-box">
                      <strong>Why it ranked here:</strong> {item.why || "No explanation available"}
                    </div>
                  </div>

                  <div className="result-price">
                    <div className="price">{item.price || "$--"}</div>
                    <div className="subtext">preferred source cost / CAD</div>
                    <div className="pill-source preferred">Safe to quote</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel">
              <h2>Live Google / SERP results</h2>
              <p className="panel-subtext">
                These rows show all returned market results. Prices are displayed when visible in the SERP response.
              </p>

              {apiError && (
                <div className="error-box">
                  <strong>API error:</strong> {apiError}
                </div>
              )}

              {serpError && (
                <div className="error-box">
                  <strong>SERP error:</strong> {serpError}
                </div>
              )}

              {loading && (
                <div className="info-box">
                  Loading live Google organic and shopping results...
                </div>
              )}

              {!loading && serpResults.length === 0 && !apiError && (
                <div className="info-box">
                  No SERP results returned yet.
                </div>
              )}

              <div className="serp-table-wrap">
                <table className="serp-table">
                  <thead>
                    <tr>
                      <th>Pos</th>
                      <th>Vendor</th>
                      <th>Type</th>
                      <th>Title</th>
                      <th>Price</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {serpResults.map((item, idx) => (
                      <tr key={`serp-${idx}`}>
                        <td>{item.position ?? idx + 1}</td>
                        <td>
                          <div className="table-strong">{item.vendor}</div>
                          <div className="table-sub">{item.domain}</div>
                        </td>
                        <td>
                          <span className="pill-source google">
                            {item.resultType || "serp"}
                          </span>
                        </td>
                        <td>
                          <div className="table-strong">{item.title}</div>
                          <div className="table-sub">{item.why}</div>
                        </td>
                        <td>{item.price || "$--"}</td>
                        <td>
                          <span className={confidencePill(item.confidence || "Low")}>
                            {item.confidence || "Low"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="side-column">
            <div className="panel">
              <h2>SERP market analysis</h2>
              <div className="summary-grid two-cols compact-grid">
                <div className="summary-card">
                  <div className="label">Total results</div>
                  <div className="value">{analysis?.totalResults ?? 0}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Priced results</div>
                  <div className="value">{analysis?.pricedResults ?? 0}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Lowest price</div>
                  <div className="value">{analysis?.lowestPrice ?? "$--"}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Highest price</div>
                  <div className="value">{analysis?.highestPrice ?? "$--"}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Average price</div>
                  <div className="value">{analysis?.averagePrice ?? "$--"}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Review count</div>
                  <div className="value">{analysis?.reviewCount ?? 0}</div>
                </div>
              </div>

              <div className="info-box">
                {analysis?.summary || "No analysis available yet."}
              </div>
            </div>

            <div className="panel">
              <h2>Quote guidance</h2>
              <div className="summary-grid two-cols compact-grid">
                <div className="summary-card">
                  <div className="label">Selected source</div>
                  <div className="value">{selected.selectedSource}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Source cost</div>
                  <div className="value">{selected.selectedCost}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Target margin</div>
                  <div className="value">{selected.targetMargin}</div>
                </div>
                <div className="summary-card">
                  <div className="label">Suggested sell price</div>
                  <div className="value">{selected.suggestedSellPrice}</div>
                </div>
              </div>

              <div className="recommend-box">
                <strong>Recommended guidance:</strong> Quote from the preferred supplier feed.
                Use SERP results to understand market spread and justify the quote.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;