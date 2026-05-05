import { useEffect, useMemo, useState } from "react";
import { API_URL } from "../search/constants";

const SOURCE_LABELS = {
  whitecap: "White Cap (distributor)",
  kms: "KMS Tools (retail)",
  canadiantire: "Canadian Tire (retail)",
  homedepot: "Home Depot (retail)"
};

const STATUS_COLORS = {
  matched: "status-good",
  partial: "status-warn",
  failed: "status-bad"
};

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeDiagnostics(payload, { source, query, requestId }) {
  const root = payload?.debug || payload?.data || payload || {};
  const metadata = root.metadata || root.connector_call || {};
  const results = asArray(root.results || root.items || root.normalized_results);
  const matchAttributes = asArray(root.match_attributes || root.matchAttributes).map((item) => ({
    attribute: item?.attribute || item?.name || "unknown",
    expected: item?.expected ?? item?.input ?? "",
    actual: item?.actual ?? "",
    scoreImpact: item?.score_impact ?? item?.points ?? 0,
    status: String(item?.status || "failed").toLowerCase()
  }));

  const confidenceBreakdown = asArray(root.confidence_breakdown || root.confidence_rules || root.rules).map((rule, idx) => ({
    id: `${rule?.rule_name || rule?.name || "rule"}-${idx}`,
    ruleName: rule?.rule_name || rule?.name || "Unnamed rule",
    condition: rule?.condition || rule?.condition_evaluated || "n/a",
    points: Number(rule?.points_added ?? rule?.points ?? 0),
    contribution: Number(rule?.final_contribution ?? rule?.contribution ?? 0)
  }));

  const thresholds = root.confidence_thresholds || {
    High: ">= 80",
    Medium: "50 - 79",
    Low: "< 50"
  };

  const status = metadata.status || (root.error ? "failed" : "success");

  return {
    metadata: {
      source: metadata.source || source,
      query: metadata.query || query,
      requestId: metadata.request_id || requestId || "",
      status,
      durationMs: metadata.duration_ms || metadata.duration || null,
      timeout: Boolean(metadata.timeout || status === "timeout"),
      error: metadata.error || root.error || ""
    },
    matchAttributes,
    results,
    confidenceBreakdown,
    thresholds
  };
}

async function fetchDiagnostics({ source, query, requestId, signal }) {
  const encodedSource = encodeURIComponent(source);
  const params = new URLSearchParams({ source, query, requestId: requestId || "" });

  const candidates = [
    { url: `${API_URL}/search/debug?${params.toString()}`, method: "GET" },
    { url: `${API_URL}/connectors/${encodedSource}/debug?${params.toString()}`, method: "GET" },
    { url: `${API_URL}/search/debug`, method: "POST", body: { source, query, request_id: requestId || null } }
  ];

  for (const candidate of candidates) {
    try {
      const response = await fetch(candidate.url, {
        method: candidate.method,
        headers: { "Content-Type": "application/json" },
        signal,
        body: candidate.body ? JSON.stringify(candidate.body) : undefined
      });
      if (!response.ok) continue;
      const payload = await response.json();
      return { diagnostics: normalizeDiagnostics(payload, { source, query, requestId }), mode: "debug-endpoint" };
    } catch {
      // Keep trying fallbacks.
    }
  }

  const fallbackResponse = await fetch(`${API_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({ query })
  });

  if (!fallbackResponse.ok) {
    throw new Error(`Unable to fetch diagnostics (backend returned ${fallbackResponse.status})`);
  }

  const fallbackPayload = await fallbackResponse.json();
  const allResults = asArray(fallbackPayload.results);
  const sourceResults = allResults.filter((item) => String(item?.source || "").toLowerCase().includes(source.toLowerCase()));

  const fallbackDiagnostic = normalizeDiagnostics(
    {
      metadata: {
        source,
        query,
        request_id: fallbackPayload.request_id || requestId || "",
        status: "success",
        duration_ms: fallbackPayload.analysis?.duration_ms,
        error: fallbackPayload.per_source_errors?.[source] || ""
      },
      match_attributes: [],
      results: sourceResults,
      confidence_breakdown: []
    },
    { source, query, requestId }
  );

  return { diagnostics: fallbackDiagnostic, mode: "search-fallback" };
}

export default function ConnectorDetailsPage({ source, query, requestId, timestamp }) {
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [diagnostics, setDiagnostics] = useState(null);
  const [mode, setMode] = useState("none");

  const sourceLabel = SOURCE_LABELS[source] || source;
  const hasRequiredContext = Boolean(source && query);

  const timestampLabel = useMemo(() => {
    if (!timestamp) return "N/A";
    const parsed = new Date(timestamp);
    return Number.isNaN(parsed.valueOf()) ? timestamp : parsed.toISOString();
  }, [timestamp]);

  useEffect(() => {
    if (!hasRequiredContext) return;
    const controller = new AbortController();
    setLoading(true);
    setFetchError("");

    fetchDiagnostics({ source, query, requestId, signal: controller.signal })
      .then((result) => {
        setDiagnostics(result.diagnostics);
        setMode(result.mode);
      })
      .catch((error) => {
        setFetchError(error?.message || "Failed to load connector diagnostics.");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [hasRequiredContext, query, requestId, source]);

  if (!hasRequiredContext) {
    return <div className="panel"><div className="error-box"><strong>Missing debug context.</strong></div></div>;
  }

  const call = diagnostics?.metadata;

  return (
    <div className="panel connector-debug-page">
      <h2>Connector Debug Details</h2>
      <div className="info-box">
        <div><strong>Source:</strong> {sourceLabel}</div>
        <div><strong>Query:</strong> {query}</div>
        <div><strong>Request ID:</strong> {requestId || "N/A"}</div>
        <div><strong>Timestamp:</strong> {timestampLabel}</div>
        <div><strong>Data mode:</strong> {mode}</div>
      </div>

      {loading && <div className="info-box">Loading connector diagnostics…</div>}
      {fetchError && <div className="error-box">{fetchError}</div>}

      {call && (
        <>
          <h3>Connector Call Metadata</h3>
          <div className="detail-grid">
            <div><strong>Status:</strong> {call.status}</div>
            <div><strong>Duration:</strong> {call.durationMs ?? "N/A"} ms</div>
            <div><strong>Timeout:</strong> {call.timeout ? "Yes" : "No"}</div>
            <div><strong>Error:</strong> {call.error || "None"}</div>
          </div>
        </>
      )}

      <h3>Legend</h3>
      <div className="source-pill-list">
        <span className="tag status-good">Matched / High confidence</span>
        <span className="tag status-warn">Partial / Medium confidence</span>
        <span className="tag status-bad">Failed / Low confidence</span>
      </div>

      <h3>Match Attributes</h3>
      {diagnostics?.matchAttributes?.length ? (
        <table className="debug-table">
          <thead><tr><th>attribute</th><th>expected/input</th><th>actual</th><th>score impact</th><th>status</th></tr></thead>
          <tbody>
            {diagnostics.matchAttributes.map((row, index) => (
              <tr key={`${row.attribute}-${index}`} className={STATUS_COLORS[row.status] || "status-bad"}>
                <td>{row.attribute}</td><td>{String(row.expected || "")}</td><td>{String(row.actual || "")}</td><td>{row.scoreImpact}</td><td>{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <div className="info-box">No explicit match-attribute details were returned.</div>}

      <h3>Confidence Breakdown</h3>
      <div className="table-sub">Thresholds: High {diagnostics?.thresholds?.High || "N/A"}, Medium {diagnostics?.thresholds?.Medium || "N/A"}, Low {diagnostics?.thresholds?.Low || "N/A"}</div>
      {diagnostics?.confidenceBreakdown?.length ? (
        <table className="debug-table">
          <thead><tr><th>Rule name</th><th>Condition evaluated</th><th>Points added/removed</th><th>Final contribution</th></tr></thead>
          <tbody>
            {diagnostics.confidenceBreakdown.map((rule) => (
              <tr key={rule.id}><td>{rule.ruleName}</td><td>{rule.condition}</td><td>{rule.points}</td><td>{rule.contribution}</td></tr>
            ))}
          </tbody>
        </table>
      ) : <div className="info-box">Confidence rule details were not returned by backend.</div>}

      <h3>Connector Results</h3>
      {call?.status === "timeout" || call?.status === "failed" ? (
        <div className="error-box">Connector call ended with status <strong>{call.status}</strong>. {call?.error || "No additional error details."}</div>
      ) : diagnostics?.results?.length ? (
        <table className="debug-table">
          <thead><tr><th>title</th><th>price_text</th><th>price_value</th><th>currency</th><th>brand</th><th>sku</th><th>availability</th><th>product_url</th><th>confidence</th><th>score</th><th>why</th></tr></thead>
          <tbody>
            {diagnostics.results.map((item, idx) => {
              const confidence = String(item?.confidence || "Low");
              const confidenceClass = confidence === "High" ? "status-good" : confidence === "Medium" ? "status-warn" : "status-bad";
              return (
                <tr key={`${item?.product_url || item?.title || "row"}-${idx}`} className={confidenceClass}>
                  <td>{item?.title || "N/A"}</td><td>{item?.price_text || "N/A"}</td><td>{item?.price_value ?? "N/A"}</td><td>{item?.currency || "N/A"}</td>
                  <td>{item?.brand || "N/A"}</td><td>{item?.sku || "N/A"}</td><td>{item?.availability || "N/A"}</td>
                  <td>{item?.product_url ? <a href={item.product_url} target="_blank" rel="noreferrer">Link</a> : "N/A"}</td>
                  <td>{confidence}</td><td>{item?.score ?? "N/A"}</td><td>{item?.why || "N/A"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : <div className="info-box">Connector responded but returned no items.</div>}
      <a className="details-link" href="/">← Back to search</a>
    </div>
  );
}
