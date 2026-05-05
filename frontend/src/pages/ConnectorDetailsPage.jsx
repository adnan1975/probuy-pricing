import { useMemo } from "react";

const SOURCE_LABELS = {
  whitecap: "White Cap (distributor)",
  kms: "KMS Tools (retail)",
  canadiantire: "Canadian Tire (retail)",
  homedepot: "Home Depot (retail)"
};

export default function ConnectorDetailsPage({ source, query, requestId, timestamp }) {
  const sourceLabel = SOURCE_LABELS[source] || source;
  const hasRequiredContext = Boolean(source && query);

  const timestampLabel = useMemo(() => {
    if (!timestamp) return "N/A";
    const parsed = new Date(timestamp);
    return Number.isNaN(parsed.valueOf()) ? timestamp : parsed.toISOString();
  }, [timestamp]);

  if (!hasRequiredContext) {
    return (
      <div className="panel">
        <div className="info-box">
          <strong>Missing debug context.</strong>
          <div>Open this page from a source card Details button after running a search.</div>
          <a className="details-link" href="/">← Back to search</a>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>Connector Debug Details</h2>
      <div className="info-box">
        <div><strong>Source:</strong> {sourceLabel}</div>
        <div><strong>Query:</strong> {query}</div>
        <div><strong>Request ID:</strong> {requestId || "N/A"}</div>
        <div><strong>Timestamp:</strong> {timestampLabel}</div>
      </div>
      <div className="table-sub">Use this context to inspect connector logs and backend traces for this source run.</div>
      <a className="details-link" href="/">← Back to search</a>
    </div>
  );
}
