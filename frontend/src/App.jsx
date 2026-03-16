import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("3M SecureFit SF201AF clear anti-fog glasses");

  useEffect(() => {
    fetch(`http://127.0.0.1:8000/search?product=${encodeURIComponent(query)}`)
      .then((res) => res.json())
      .then((data) => setResults(data.results || []))
      .catch((err) => console.error("API error:", err));
  }, [query]);

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
              Search industrial and safety products across supplier feeds and live market
              sources, compare vendor pricing, and rank listings using ProBuy business priority,
              relevance, and confidence.
            </p>
          </div>
          <div className="top-actions">
            <button className="secondary-btn">Save Quote View</button>
            <button className="primary-btn">Approve Sell Price</button>
          </div>
        </div>

        <div className="search-box">
          <input value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="primary-btn">Search</button>
        </div>

        <div className="summary-grid">
          <div className="summary-card">
            <div className="label">Customer</div>
            <div className="value">West Coast Marine</div>
          </div>
          <div className="summary-card">
            <div className="label">Brand</div>
            <div className="value">3M</div>
          </div>
          <div className="summary-card">
            <div className="label">Part Number</div>
            <div className="value">SF201AF</div>
          </div>
          <div className="summary-card">
            <div className="label">Category</div>
            <div className="value">PPE / Safety Eyewear</div>
          </div>
          <div className="summary-card">
            <div className="label">Results</div>
            <div className="value">{results.length} listings</div>
          </div>
          <div className="summary-card">
            <div className="label">Lowest seen</div>
            <div className="value">$11.80</div>
          </div>
        </div>

        <div className="main-grid">
          <div className="panel">
            <div className="panel-header">
              <div>
                <h2>Ranked supplier listings</h2>
                <p>
                  Weighted by search relevance, ProBuy supplier priority, exact part-number match,
                  freshness, availability, and commercial value.
                </p>
              </div>
            </div>

            <div className="results-list">
              {results.map((item, idx) => (
                <div className="result-row" key={idx}>
                  <div className="result-main">
                    <div className="result-top">
                      <span className="vendor-name">{item.vendor}</span>
                      <span className="badge">{item.badge}</span>
                      <span className={scorePill(item.score)}>Score {item.score}</span>
                      <span className={confidencePill(item.confidence)}>
                        {item.confidence} confidence
                      </span>
                    </div>

                    <div className="title">{item.title}</div>

                    <div className="meta">
                      <span>MPN/SKU: {item.sku}</span>
                      <span>{item.stock}</span>
                      <span>Updated {item.freshness}</span>
                    </div>
                  </div>

                  <div className="result-price">
                    <div className="price">${item.price.toFixed(2)}</div>
                    <div className="subtext">each / CAD</div>
                    <div className="row-actions">
                      <button className="secondary-btn small">Open source</button>
                      <button className="primary-btn small">Use in quote</button>
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
                SCN Industrial is ranked #1 for ProBuy because it has an exact manufacturer part
                match, strong freshness, and the highest supplier priority. Grainger Canada is a
                close market benchmark. Amazon Business is cheaper but the listing confidence is
                low and should not be used without manual review.
              </div>
            </div>

            <div className="panel">
              <h2>Quote pricing panel</h2>
              <div className="summary-grid two-cols">
                <div className="summary-card">
                  <div className="label">Selected source</div>
                  <div className="value">SCN Industrial</div>
                </div>
                <div className="summary-card">
                  <div className="label">Source cost</div>
                  <div className="value">$13.10</div>
                </div>
                <div className="summary-card">
                  <div className="label">Target margin</div>
                  <div className="value">32%</div>
                </div>
                <div className="summary-card">
                  <div className="label">Suggested sell price</div>
                  <div className="value">$19.25</div>
                </div>
              </div>

              <div className="input-group">
                <label>Final approved quote price</label>
                <input value="$19.25" readOnly />
              </div>

              <button className="primary-btn full">Save pricing decision</button>
            </div>

            <div className="panel">
              <h2>Supplier weights</h2>
              <div className="providers">
                <div className="provider-row">
                  <div>
                    <div className="provider-name">SCN Industrial Feed</div>
                    <div className="subtext">Status: Active</div>
                  </div>
                  <div className="weight">+18</div>
                </div>
                <div className="provider-row">
                  <div>
                    <div className="provider-name">Grainger Canada</div>
                    <div className="subtext">Status: Active</div>
                  </div>
                  <div className="weight">+10</div>
                </div>
                <div className="provider-row">
                  <div>
                    <div className="provider-name">Acklands-Grainger</div>
                    <div className="subtext">Status: Active</div>
                  </div>
                  <div className="weight">+8</div>
                </div>
                <div className="provider-row">
                  <div>
                    <div className="provider-name">Google Shopping / DataForSEO</div>
                    <div className="subtext">Status: Active</div>
                  </div>
                  <div className="weight">+4</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;