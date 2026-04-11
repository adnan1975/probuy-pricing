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
  onRetryDetails
}) {
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
      {!loading && !apiError && canSearch && visibleResults.length === 0 && (
        <div className="info-box">No connector matches were found for this query.</div>
      )}
      {!loading && !apiError && canSearch && visibleResults.length > 0 && (analysis?.priced_results ?? 0) === 0 && (
        <div className="info-box">No price could be found yet. Items are shown with defaults so you can still compare sources.</div>
      )}

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

      <div className="retailer-table-wrap">
        <table className="retailer-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Source</th>
              <th>Model</th>
              <th>Manufacturer</th>
              <th>Manufacturer Model</th>
              <th>Distributor Cost</th>
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
              const rowDetails = detailsState[String(idx)] || {};
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
                    <td>{item.model || item.sku || "N/A"}</td>
                    <td>{item.brand || "N/A"}</td>
                    <td>{item.manufacturer_model || "N/A"}</td>
                    <td>{formatCurrency(item.distributor_cost)}</td>
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
                      <button
                        className="details-btn"
                        type="button"
                        onClick={() => onToggleDetails(idx)}
                      >
                        {isExpanded ? "Hide Details" : "Details"}
                      </button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="details-row">
                      <td colSpan={13}>
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
                                  <ol className="status-list">
                                    {connectorStatus.steps.map((step, stepIndex) => (
                                      <li key={`${connector.source}-step-${stepIndex}`}>{step}</li>
                                    ))}
                                  </ol>
                                )}
                                {!isLoading && (connectorStatus.state === "success" || connectorStatus.state === "failed") && (
                                  <div className={`status-footer ${connectorStatus.state}`}>
                                    {connectorStatus.state === "success" ? "Status: Success" : "Status: Failed"}
                                  </div>
                                )}
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
                        <div className="details-actions">
                          <button
                            className="details-btn"
                            type="button"
                            onClick={() => onRetryDetails(idx)}
                            disabled={Boolean(rowDetails.loadingAll)}
                          >
                            Retry all connectors
                          </button>
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
  );
}
