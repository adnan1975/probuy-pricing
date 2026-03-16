import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const examples = [
  {
    id: "grinder",
    label: "DEWALT FlexVolt Grinder",
    customer: "West Coast Marine",
    query: "Flexvolt Perform & Protect Max Brushless Cordless Grinder",
    brand: "DEWALT",
    partNumber: "DCG418B",
    category: "Power Tools / Grinders",
    summary:
      "This example shows how ProBuy compares a preferred supplier feed against live market results and flags looser Google matches for manual review.",
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
      "This example shows how ProBuy separates exact product matches from broader Google-discovered market references.",
    selectedSource: "SCN Industrial",
    selectedCost: "$13.10",
    targetMargin: "32%",
    suggestedSellPrice: "$19.25"
  }
];

function App() {
  const [selectedExampleId, setSelectedExampleId] = useState("grinder");
  const [results, setResults] = useState([]);
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
        const res = await fetch(
          `${API_URL}/search?product=${encodeURIComponent(selected.query)}`,
          { signal: controller.signal }
        );

        if (!res.ok) {
          throw new Error(`Backend returned ${res.status}`);
        }

        const data = await res.json();
        setResults(Array.isArray(data.results) ? data.results : []);
      } catch (err) {
        if (err.name !== "AbortError") {
          console.error("API error:", err);
          setApiError(err.message || "Could not load results");
          setResults([]);
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

  const providerToneClasses = {
    preferred: "provider preferred",
    google: "provider google",
    competitor: "provider competitor",
    review: "provider review"
  };

  const providers = [
    {
      name: "SCN Industrial Feed",
      weight: "+18",
      description: "Preferred supplier pricing and strongest operational trust",
      tone: "preferred"
    },
    {
      name: "Google SERP / Shopping",
      weight: "+4",
      description: "Live market discovery for pricing context and competitor visibility",
      tone: "google"
    },
    {
      name: "Retail Competitors",
      weight: "+2",
      description: "Commercial benchmarks such as KMS Tools or similar listings",
      tone: "competitor"
    },
    {
      name: "Manual Review Queue",
      weight: "Flag",
      description: "Low-confidence results that should not be quoted directly",
      tone: "review"
    }
  ];

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

  const sourceTypeLabel = (type) => {
    if (type === "preferred") return "Safe to quote";
    if (type === "review") return "Review before quote";
    return "Benchmark / validate";
  };

  const bestMarketPrice =
    results.length > 0 ? results[results.length - 1]?.price || "$--" : "$--";

  return (
    <div className="page">
      <div className="container">
        <div className="topbar">
          <div>
            <div className="tag">ProBuy Pricing Console</div>
            <h1>AI-assisted sourcing and pricing search</h1>
            <p>
              Compare preferred supplier pricing against live Google market discovery,
              show users exactly where each price came from, and highlight which results
              are safe to quote.
            </p>
          </div>

          <div className="help-card">
            <div className="help-title">How to read this screen</div>
            <div>
              Green = trusted supplier feed, blue = Google-discovered result,
              amber = market benchmark, red = review before quoting.
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
            <div className="label">Results</div>
            <div className="value">{loading ? "Loading..." : `${results.length} listings`}</div>
          </div>
          <div className="summary-card">
            <div className="label">Best market price</div>
            <div className="value">{bestMarketPrice}</div>
          </div>
        </div>

        <div className="main-grid">
          <div className="panel">
            <div className="panel-header">
              <div>
                <h2>Ranked supplier and market listings</h2>
                <p>
                  Each row clearly identifies whether the price came from a preferred
                  supplier feed, a Google result, a competitor benchmark, or a low-confidence
                  review queue.
                </p>
              </div>
            </div>

            {apiError && (
              <div className="error-box">
                <strong>API error:</strong> {apiError}
              </div>
            )}

            {loading && (
              <div className="info-box">
                Loading live pricing and market benchmark results...
              </div>
            )}

            {!loading && results.length === 0 && !apiError && (
              <div className="info-box">
                No results returned from the backend yet.
              </div>
            )}

            <div className="results-list">
              {results.map((item, idx) => (
                <div className="result-row" key={`${item.vendor}-${idx}`}>
                  <div className="result-main">
                    <div className="result-top">
                      <span className="vendor-name">{item.vendor}</span>

                      <span
                        className={
                          toneClasses[item.sourceType] || "pill-source google"
                        }
                      >
                        {item.source || "Source"}
                      </span>

                      <span className={scorePill(item.score || 0)}>
                        Score {item.score ?? "--"}
                      </span>

                      <span className={confidencePill(item.confidence || "Low")}>
                        {item.confidence || "Low"} confidence
                      </span>
                    </div>

                    <div className="title">{item.title}</div>

                    <div className="detail-grid">
                      <div>MPN / SKU: {item.sku || "Validation needed"}</div>
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
                    <div className="subtext">estimated listing price / CAD</div>

                    <div
                      className={
                        toneClasses[item.sourceType] || "pill-source google"
                      }
                    >
                      {sourceTypeLabel(item.sourceType)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="side-column">
            <div className="panel">
              <h2>AI sourcing insight</h2>
              <div className="info-box">
                {selected.id === "grinder"
                  ? "SCN Industrial ranks first because it is your preferred source and the product identity is strongest. Google-discovered results are useful for market context, but they should be treated as benchmarks unless the product page confirms the exact model and kit contents."
                  : "SCN Industrial remains the best operational choice because it combines exact product identity with supplier priority. Google results improve price awareness, but weaker matches should not be used directly for quoting without product verification."}
              </div>
            </div>

            <div className="panel">
              <h2>Quote guidance</h2>
              <div className="summary-grid two-cols">
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
                <strong>Recommended demo message:</strong> Use preferred supplier pricing
                for quoting, and use Google-discovered results as market intelligence
                unless the exact product page is verified.
              </div>
            </div>

            <div className="panel">
              <h2>Source legend and weighting</h2>
              <div className="providers">
                {providers.map((provider) => (
                  <div
                    key={provider.name}
                    className={providerToneClasses[provider.tone] || "provider google"}
                  >
                    <div>
                      <div className="provider-name">{provider.name}</div>
                      <div className="provider-description">{provider.description}</div>
                    </div>
                    <div className="weight">{provider.weight}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;