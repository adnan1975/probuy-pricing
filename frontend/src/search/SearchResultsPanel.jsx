import { Fragment } from "react";
import { detailConnectorConfigs, PAGE_SIZE_OPTIONS } from "./constants";
import loaderImage from "../assets/results-loader.svg";

export function SearchResultsPanel({
  apiError,
  loading,
  canSearch,
  visibleResults,
  analysis,
  totalResults,
  page,
  totalPages,
  pageSize,
  setPage,
  onPageSizeChange,
  detailsState,
  expandedRows,
  relatedOffersByRow,
  formatCurrency,
  formatSuggestedPrice,
  onToggleDetails,
  onRetryConnector
}) {
  const hasVisibleResults = visibleResults.length > 0;

  return (
    <div className="panel">
      <h2>Items found</h2>
      {apiError && <div className="error-box"><strong>API error:</strong> {apiError}</div>}
      {loading && (
        <div className="info-box inline-loader">
          <img src={loaderImage} alt="Loading results" className="results-loader-image" />
          Loading primary connector pricing...
        </div>
      )}
      {!loading && !apiError && canSearch && !hasVisibleResults && (
        <div className="info-box">No connector matches were found for this query.</div>
      )}
      {!loading && !apiError && canSearch && hasVisibleResults && (analysis?.priced_results ?? 0) === 0 && (
        <div className="info-box">No price could be found yet. Items are shown with defaults so you can still compare sources.</div>
      )}

      {hasVisibleResults && (
        <div className="pagination-controls">
          <div>
            Showing <strong>{visibleResults.length}</strong> of <strong>{totalResults}</strong> results
          </div>
          <label>
            Page size
            <select value={pageSize} onChange={(e) => onPageSizeChange(e.target.value)}>
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
      )}

      {hasVisibleResults && (
        <div className="results-grid">
          {visibleResults.map((item, idx) => {
            const rank = (page - 1) * pageSize + idx + 1;
            const isBestMatch = rank === 1;
            const rowKey = `${item.source}-${idx}`;
            const relatedOffers = relatedOffersByRow[idx] || [];
            const rowDetails = detailsState[String(idx)] || {};
            const isExpanded = Boolean(expandedRows[idx]);
            return (
              <div className={`result-card ${isBestMatch ? "best-match-card" : ""}`} key={rowKey}>
                <div className="result-card-header">
                  <div className="result-card-rank">
                    #{rank}
                    {isBestMatch && <span className="best-match-badge">Best Match</span>}
                  </div>
                  <div className="result-card-source-wrap">
                    <div className="result-card-source">{item.source}</div>
                    <span className={`pill ${item.source_type === "distributor" ? "green" : "blue"}`}>
                      {item.source_type || "retail"}
                    </span>
                  </div>
                </div>

                <div className="result-card-title" title={item.title}>{item.title}</div>
                <div className="result-card-price">
                  {item.price_text || "Price unavailable"}
                </div>

                <div className="result-card-meta">
                  <div className="result-card-meta-item"><span className="table-sub">Brand</span>{item.brand || "N/A"}</div>
                  <div className="result-card-meta-item"><span className="table-sub">Model</span>{item.model || item.sku || "N/A"}</div>
                  <div className="result-card-meta-item"><span className="table-sub">SKU</span>{item.sku || "N/A"}</div>
                  <div className="result-card-meta-item"><span className="table-sub">Availability</span>{item.availability || "Unknown"}</div>
                  <div className="result-card-meta-item"><span className="table-sub">Distributor Cost</span>{formatCurrency(item.distributor_cost)}</div>
                  <div className="result-card-meta-item"><span className="table-sub">Warehouse</span>{item.location || item.warehouse_location || item.warehouse || "N/A"}</div>
                </div>

                <div className="suggested-price">Suggested Price: {formatSuggestedPrice(item, idx)}</div>
                <div className="result-card-actions">
                  <button className="publish-btn" type="button">
                    Publish Price
                  </button>
                  <button
                    className="details-btn"
                    type="button"
                    onClick={() => onToggleDetails(idx)}
                  >
                    {isExpanded ? "Hide Details" : "Details"}
                  </button>
                </div>

                {isExpanded && (
                  <Fragment>
                    <div className="details-title">Connector prices for {item.sku || item.title}</div>
                    <div className="details-grid">
                      {detailConnectorConfigs.map((connector) => {
                        const offer = rowDetails.offersBySource?.[connector.source] || null;
                        const isLoading = Boolean(rowDetails.loadingBySource?.[connector.source]);
                        const error = rowDetails.errorsBySource?.[connector.source];
                        const connectorStatus = rowDetails.statusBySource?.[connector.source] || { steps: [], state: "idle" };
                        return (
                          <div className="details-card" key={connector.source}>
                            <div className="table-strong">{connector.source}</div>
                            {isLoading ? (
                              <div className="details-loader"><span className="spinner" /> Loading...</div>
                            ) : (
                              <div>{offer?.price_text || "Price unavailable"}</div>
                            )}
                            <div className="table-sub">
                              {offer?.availability || (error ? `Error: ${error}` : "Waiting for connector")}
                            </div>
                            {connectorStatus.steps.length > 0 && (
                              <div className="status-list">
                                Status: {connectorStatus.steps[connectorStatus.steps.length - 1]}
                              </div>
                            )}
                            {!isLoading && (connectorStatus.state === "success" || connectorStatus.state === "failed") && (
                              <div className={`status-footer ${connectorStatus.state}`}>
                                {connectorStatus.state === "success" ? "Status: Success" : "Status: Failed"}
                              </div>
                            )}
                            <button
                              className="details-btn"
                              type="button"
                              onClick={() => onRetryConnector(idx, connector.source)}
                              disabled={isLoading}
                            >
                              Retry {connector.source}
                            </button>
                            {offer?.product_url && (
                              <a
                                className="details-link"
                                href={offer.product_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open details ↗
                              </a>
                            )}
                          </div>
                        );
                      })}
                      {!rowDetails.loadingAll && relatedOffers.length === 0 && (
                        <div className="details-card details-empty">
                          <div className="table-strong">No connector prices found</div>
                          <div className="table-sub">Connectors returned no priced matches for this item.</div>
                        </div>
                      )}
                    </div>
                  </Fragment>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
