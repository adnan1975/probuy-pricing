import { Fragment, useMemo, useState } from "react";
import { detailConnectorConfigs, PAGE_SIZE_OPTIONS } from "./constants";
import loaderImage from "../assets/results-loader.svg";
import ProductCompareCard from "./ProductCompareCard";

function buildWebpFallbackUrl(imageUrl) {
  if (!imageUrl) return "";
  const [baseWithPath, hashFragment = ""] = imageUrl.split("#");
  const [basePath, queryString = ""] = baseWithPath.split("?");

  if (!/\.jpe?g$/i.test(basePath)) {
    return "";
  }

  const webpPath = basePath.replace(/\.jpe?g$/i, ".webp");
  const querySuffix = queryString ? `?${queryString}` : "";
  const hashSuffix = hashFragment ? `#${hashFragment}` : "";
  return `${webpPath}${querySuffix}${hashSuffix}`;
}

function buildWebpTimestampFallbackUrl(imageUrl) {
  if (!imageUrl) return "";
  const [baseWithPath, hashFragment = ""] = imageUrl.split("#");
  const [basePath] = baseWithPath.split("?");
  const unixTimestamp = 1776062528;
  const hashSuffix = hashFragment ? `#${hashFragment}` : "";
  return `${basePath}?${unixTimestamp}${hashSuffix}`;
}

function buildQuestionMarkFallbackUrl(imageUrl) {
  if (!imageUrl) return "";
  const [baseWithPath, hashFragment = ""] = imageUrl.split("#");
  const [basePath] = baseWithPath.split("?");
  const hashSuffix = hashFragment ? `#${hashFragment}` : "";

  return `${basePath}?${hashSuffix}`;
}

function buildFolderVariantUrl(imageUrl, targetFolder) {
  if (!imageUrl) return "";
  const [baseWithPath, hashFragment = ""] = imageUrl.split("#");
  const [basePath, queryString = ""] = baseWithPath.split("?");
  const replacedPath = basePath.replace(/\/xlarge\//i, `/${targetFolder}/`);

  if (replacedPath === basePath) {
    return "";
  }

  const querySuffix = queryString ? `?${queryString}` : "";
  const hashSuffix = hashFragment ? `#${hashFragment}` : "";
  return `${replacedPath}${querySuffix}${hashSuffix}`;
}

function ProductImage({ src, alt }) {
  const [imageSrc, setImageSrc] = useState(src);
  const [fallbackIndex, setFallbackIndex] = useState(0);
  const fallbackSequence = useMemo(() => {
    const largeUrl = buildFolderVariantUrl(src, "large");
    const largeWebpUrl = buildWebpFallbackUrl(largeUrl);
    const largeWebpQuestionUrl = buildQuestionMarkFallbackUrl(largeWebpUrl);
    const largeWebpTimestampUrl = buildWebpTimestampFallbackUrl(largeWebpQuestionUrl);
    const xlargeUrl = buildFolderVariantUrl(src, "xlarge") || src;
    const xlargeWebpUrl = buildWebpFallbackUrl(xlargeUrl);
    const xlargeWebpQuestionUrl = buildQuestionMarkFallbackUrl(xlargeWebpUrl);
    const xlargeWebpTimestampUrl = buildWebpTimestampFallbackUrl(xlargeWebpQuestionUrl);

    return [
      largeUrl,
      largeWebpUrl,
      largeWebpQuestionUrl,
      largeWebpTimestampUrl,
      xlargeUrl,
      xlargeWebpUrl,
      xlargeWebpQuestionUrl,
      xlargeWebpTimestampUrl
    ].filter(Boolean);
  }, [src]);

  if (!imageSrc) {
    return (
      <div className="result-card-image-placeholder" aria-label="No image available">
        No image
      </div>
    );
  }

  const handleImageError = () => {
    const nextFallback = fallbackSequence[fallbackIndex];
    if (nextFallback && nextFallback !== imageSrc) {
      setImageSrc(nextFallback);
      setFallbackIndex((currentIndex) => currentIndex + 1);
      return;
    }

    setImageSrc("");
  };

  return (
    <img
      className="result-card-image"
      src={imageSrc}
      alt={alt}
      loading="lazy"
      onError={handleImageError}
    />
  );
}

export function SearchResultsPanel({
  apiError,
  loading,
  activeQuery = "",
  canSearch,
  hasActiveSearch = false,
  hasCompletedSearchRequest = false,
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
  onRetryConnector,
  onPushShopifyDraft,
  publishingRowState = {},
  onClearFilters,
  onUseExampleQuery
}) {
  function getPublicationInfo(item) {
    const publications = Array.isArray(item?.product_channel_publications)
      ? item.product_channel_publications
      : [];
    const shopifyPublication = publications.find((entry) => entry?.channel_code === "shopify") || null;
    const statusValue = (shopifyPublication?.publication_status || item?.publication_status || "").toUpperCase();
    const statusMap = {
      NOT_PUBLISHED: "Not Published",
      DRAFT: "Draft Created",
      PUBLISHED: "Published",
      FAILED: "Failed",
      NEEDS_REVIEW: "Needs Review"
    };
    return {
      statusValue,
      statusLabel: statusMap[statusValue] || "Not Published",
      lastError: shopifyPublication?.last_error || item?.last_error || ""
    };
  }
  const analysisMetrics = {
    totalResults: Number(analysis?.total_results ?? totalResults ?? 0),
    pricedResults: Number(analysis?.priced_results ?? 0),
    lowestPrice: analysis?.lowest_price,
    highestPrice: analysis?.highest_price,
    averagePrice: analysis?.average_price,
    sourceWarnings: Object.keys(analysis?.per_source_warnings || {}).length,
    sourceErrors: Object.keys(analysis?.per_source_errors || {}).length,
  };

  const sourceWarnings = analysis?.per_source_warnings || {};
  const sourceErrors = analysis?.per_source_errors || {};
  const hasSourceHealth = Object.keys(sourceWarnings).length > 0 || Object.keys(sourceErrors).length > 0;

  const hasVisibleResults = visibleResults.length > 0;
  const loadingQueryLabel = activeQuery || "your query";
  const skeletonRows = Array.from({ length: 6 }, (_, index) => index);

  return (
    <div className="panel">
      {!hasActiveSearch && (
        <div className="info-box muted-box">
          <strong>Start a product search</strong>
          <div>Search by model, manufacturer, SKU, or part number.</div>
          <div className="search-hint-pills">
            <span className="pill blue">DEWALT FLEXVOLT grinder DCG418B</span>
            <span className="pill blue">3M SecureFit SF201AF</span>
          </div>
        </div>
      )}
      {hasActiveSearch && <h2>Items found</h2>}
      {hasActiveSearch && !loading && !apiError && (
        <div className="kpi-dashboard" aria-label="Search KPI dashboard">
          <div className="kpi-card">
            <div className="kpi-label">Total Results</div>
            <div className="kpi-value">{analysisMetrics.totalResults}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Priced Results</div>
            <div className="kpi-value">{analysisMetrics.pricedResults}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Lowest Price</div>
            <div className="kpi-value">{formatCurrency(analysisMetrics.lowestPrice)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Highest Price</div>
            <div className="kpi-value">{formatCurrency(analysisMetrics.highestPrice)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Average Price</div>
            <div className="kpi-value">{formatCurrency(analysisMetrics.averagePrice)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Source Health</div>
            <div className="kpi-value">
              <span className={`pill ${analysisMetrics.sourceErrors > 0 ? "red" : "green"}`}>
                {analysisMetrics.sourceErrors} error(s)
              </span>
              <span className={`pill ${analysisMetrics.sourceWarnings > 0 ? "amber" : "green"}`}>
                {analysisMetrics.sourceWarnings} warning(s)
              </span>
            </div>
          </div>
        </div>
      )}
      {hasSourceHealth && !loading && !apiError && (
        <div className="kpi-source-health">
          {Object.entries(sourceWarnings).map(([source, warning]) => (
            <div className="info-box" key={`warning-${source}`}>
              <strong>{source} warning:</strong> {warning}
            </div>
          ))}
          {Object.entries(sourceErrors).map(([source, error]) => (
            <div className="error-box" key={`error-${source}`}>
              <strong>{source} error:</strong> {error}
            </div>
          ))}
        </div>
      )}
      {apiError && <div className="error-box"><strong>API error:</strong> {apiError}</div>}
      {loading && (
        <div className="info-box inline-loader" aria-live="polite">
          <img src={loaderImage} alt="Loading results" className="results-loader-image" />
          Searching for "{loadingQueryLabel}"...
        </div>
      )}
      {!loading && !apiError && canSearch && hasCompletedSearchRequest && !hasVisibleResults && (
        <div className="info-box">
          <strong>No matches found for "{activeQuery}".</strong>
          <ul>
            <li>Try fewer words</li>
            <li>Try SKU/part number</li>
            <li>Check spelling</li>
            <li>Remove filters</li>
          </ul>
          <div className="result-card-actions">
            <button className="publish-btn" type="button" onClick={onClearFilters}>
              Clear filters
            </button>
            <button className="publish-btn" type="button" onClick={onUseExampleQuery}>
              Use example query
            </button>
          </div>
        </div>
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

      {loading && (
        <div className="results-grid" aria-busy="true" aria-live="polite" aria-label={`Loading results for ${loadingQueryLabel}`}>
          {skeletonRows.map((row) => (
            <div className="result-card result-card-skeleton" key={`skeleton-${row}`} aria-hidden="true">
              <div className="skeleton-line skeleton-line-short" />
              <div className="skeleton-line skeleton-line-title" />
              <div className="skeleton-line skeleton-line-price" />
              <div className="result-card-meta">
                <div className="result-card-meta-item skeleton-block" />
                <div className="result-card-meta-item skeleton-block" />
                <div className="result-card-meta-item skeleton-block" />
                <div className="result-card-meta-item skeleton-block" />
              </div>
              <div className="result-card-actions">
                <div className="skeleton-line skeleton-line-button" />
                <div className="skeleton-line skeleton-line-button" />
              </div>
            </div>
          ))}
        </div>
      )}

      {hasVisibleResults && (
        <div className="results-grid" aria-busy={loading ? "true" : "false"}>
          {visibleResults.map((item, idx) => {
            const rank = (page - 1) * pageSize + idx + 1;
            const isBestMatch = rank === 1;
            const rowKey = `${item.source}-${idx}`;
            const relatedOffers = relatedOffersByRow[idx] || [];
            const rowDetails = detailsState[String(idx)] || {};
            const isExpanded = Boolean(expandedRows[idx]);
            const productImage = typeof item.primary_image === "string" && item.primary_image.trim()
              ? item.primary_image.trim().toLowerCase()
              : (typeof item.image_url === "string" ? item.image_url.trim() : "");
            const metaRows = [
              [
                { label: "Brand", value: item.brand || "N/A" },
                { label: "Model", value: item.model_number || item.model || item.sku || "N/A" }
              ],
              [
                { label: "ID", value: item.source_product_id || item.sourceProductId || "N/A" },
                { label: "Distributor Cost", value: formatCurrency(item.distributor_cost) },
              ],
              [
                { label: "Source Category", value: item.source_type === "distributor" ? "Distributor" : item.source_type === "retail" ? "Retail" : "N/A" }
              ],
              [
                (() => {
                  const publication = getPublicationInfo(item);
                  return {
                    label: "Shopify Status",
                    value: publication.statusLabel
                  };
                })(),
                {
                  label: "Channel",
                  value: (() => {
                    const publicationStatus = typeof item.is_published === "boolean"
                      ? (item.is_published ? "PUBLISHED" : "NOT_PUBLISHED")
                      : (item.publication_status || "");
                    if (publicationStatus === "NOT_PUBLISHED") {
                      return "—";
                    }
                    return item.channel_code || "N/A";
                  })()
                }
              ]
            ];
            const sourceProductId = item.source_product_id || item.sourceProductId || "";
            const isPublishing = Boolean(publishingRowState[sourceProductId]);
            const publication = getPublicationInfo(item);
            return (
              <div className={`result-card ${isBestMatch ? "best-match-card" : ""}`} key={rowKey}>
                <div className="result-card-image-grid">
                  <ProductImage key={productImage || "no-image"} src={productImage} alt={item.title || "Product image"} />
                </div>

                <div className="result-card-header">
                  <div className="result-card-rank">
                    #{rank}
                    {isBestMatch && <span className="best-match-badge">Best Match</span>}
                  </div>
                  <div className="result-card-source-wrap">
                    <div className="result-card-source">{item.source_code || item.sourceCode || item.source}</div>
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
                  {metaRows.map((metaRow, rowIndex) => (
                    <div className="result-card-meta-row" key={`meta-row-${rowIndex}`}>
                      {metaRow.map((metaItem) => (
                        <div className="result-card-meta-item" key={metaItem.label}>
                          <span className="table-sub">{metaItem.label}</span>
                          {metaItem.value}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>

                <div className="suggested-price">Suggested Price: {formatSuggestedPrice(item, idx)}</div>
                <div className="result-card-actions">
                  <button
                    className="publish-btn"
                    type="button"
                    disabled={isPublishing || !sourceProductId}
                    onClick={() => onPushShopifyDraft?.(item)}
                  >
                    {isPublishing ? "Publishing..." : "Publish"}
                  </button>
                  <button
                    className="details-btn"
                    type="button"
                    onClick={() => onToggleDetails(idx)}
                  >
                    {isExpanded ? "Hide Competitor Pricing" : "Get Competitor Pricing"}
                  </button>
                </div>
                {(publication.statusValue === "FAILED" || publication.statusValue === "NEEDS_REVIEW") && publication.lastError && (
                  <div className="table-sub">Issue: {publication.lastError}</div>
                )}

                {isExpanded && (
                  <Fragment>
                    <div className="details-section">
                    <div className="details-title">Connector prices for {item.sku || item.title}</div>
                    <div className="details-grid">
                      {detailConnectorConfigs.map((connector) => {
                        const offer = rowDetails.offersBySource?.[connector.source] || null;
                        const isLoading = Boolean(rowDetails.loadingBySource?.[connector.source]);
                        const error = rowDetails.errorsBySource?.[connector.source];
                        const connectorStatus = rowDetails.statusBySource?.[connector.source] || { steps: [], state: "idle" };
                        const comparison = rowDetails.matchBySource?.[connector.source] || null;
                        const statusMessage = offer?.availability
                          || (error ? `Error: ${error}` : connectorStatus.state === "failed" ? "Connector failed to return price" : "No availability update");
                        const mismatchMessage = comparison?.isBelowThreshold ? comparison.thresholdText : "";
                        const whyMessage = comparison?.isBelowThreshold
                          ? "Why: KMS offer is shown for transparency but excluded from suggested price by default."
                          : "";
                        return (
                          <div className="details-card" key={connector.source}>
                            <div className="table-strong">{connector.source}</div>
                            {isLoading ? (
                              <div className="details-loader"><span className="spinner" /> Loading...</div>
                            ) : (
                              <div>{offer?.price_text || "Price unavailable"}</div>
                            )}
                            <div className="table-sub">
                              {statusMessage}
                            </div>
                            {mismatchMessage && (
                              <div className="table-sub">{mismatchMessage}</div>
                            )}
                            {whyMessage && (
                              <div className="table-sub">{whyMessage}</div>
                            )}
                            <ProductCompareCard comparison={comparison} />
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
                                View competitor listing ↗
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
