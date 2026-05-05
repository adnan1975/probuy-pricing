import { useEffect, useMemo, useState } from "react";
import { API_URL } from "../search/constants";

const SOURCE_CONFIG = {
  kms: {
    label: "KMS Tools",
    connectorName: "kms_tools",
    sourceType: "retail benchmark"
  },
  kms_tools: {
    label: "KMS Tools",
    connectorName: "kms_tools",
    sourceType: "retail benchmark"
  },
  kmstools: {
    label: "KMS Tools",
    connectorName: "kms_tools",
    sourceType: "retail benchmark"
  },
  whitecap: {
    label: "White Cap",
    connectorName: "whitecap",
    sourceType: "distributor / primary quoting source"
  },
  canadiantire: {
    label: "Canadian Tire",
    connectorName: "canadiantire",
    sourceType: "retail benchmark"
  },
  homedepot: {
    label: "Home Depot",
    connectorName: "homedepot",
    sourceType: "retail benchmark"
  }
};

function normalizeSource(source) {
  return String(source || "kms_tools").trim().toLowerCase().replace(/[-\s]+/g, "_");
}

function getSourceConfig(source) {
  const normalizedSource = normalizeSource(source);
  return SOURCE_CONFIG[normalizedSource] || SOURCE_CONFIG[normalizedSource.replace(/_/g, "")] || SOURCE_CONFIG.kms_tools;
}

function asPrettyJson(value) {
  if (value === null || typeof value === "undefined") {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

function firstNonEmpty(...values) {
  return values.find((value) => typeof value === "string" && value.trim())?.trim() || "";
}

function buildConnectorQuery(product) {
  return firstNonEmpty(
    product?.description,
    product?.title,
    product?.source_product_key,
    product?.source_model_no,
    product?.model_number,
    product?.sku,
    product?.model,
    product?.manufacturer_model
  );
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.headers || {})
    }
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || `Request failed with ${response.status}`);
  }

  return response.json();
}

async function fetchProductDetails(productId, signal) {
  const encodedProductId = encodeURIComponent(productId);
  return fetchJson(`${API_URL}/api/products/${encodedProductId}`, { signal });
}

async function postConnectorSearch({ connectorName, query, signal }) {
  return fetchJson(`${API_URL}/search/${encodeURIComponent(connectorName)}`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query })
  });
}

export default function ConnectorDetailsPage({ source = "kms_tools", productId }) {
  const sourceConfig = useMemo(() => getSourceConfig(source), [source]);
  const [productLoading, setProductLoading] = useState(false);
  const [productError, setProductError] = useState("");
  const [product, setProduct] = useState(null);
  const [connectorLoading, setConnectorLoading] = useState(false);
  const [connectorError, setConnectorError] = useState("");
  const [connectorResponse, setConnectorResponse] = useState(null);

  const hasProductId = Boolean(productId);
  const connectorQuery = useMemo(() => buildConnectorQuery(product), [product]);

  useEffect(() => {
    if (!hasProductId) return undefined;

    const controller = new AbortController();
    setProductLoading(true);
    setProductError("");
    setProduct(null);
    setConnectorResponse(null);
    setConnectorError("");

    fetchProductDetails(productId, controller.signal)
      .then((payload) => setProduct(payload))
      .catch((error) => {
        if (error?.name !== "AbortError") {
          setProductError(error?.message || "Failed to load product details from database.");
        }
      })
      .finally(() => setProductLoading(false));

    return () => controller.abort();
  }, [hasProductId, productId]);

  async function handleStart() {
    if (!connectorQuery) {
      setConnectorError("Product details do not include a description, title, SKU, or model to send to the connector.");
      return;
    }

    const controller = new AbortController();
    setConnectorLoading(true);
    setConnectorError("");
    setConnectorResponse(null);

    try {
      const payload = await postConnectorSearch({
        connectorName: sourceConfig.connectorName,
        query: connectorQuery,
        signal: controller.signal
      });
      setConnectorResponse(payload);
    } catch (error) {
      if (error?.name !== "AbortError") {
        setConnectorError(error?.message || `Failed to run ${sourceConfig.label} connector.`);
      }
    } finally {
      setConnectorLoading(false);
    }
  }

  if (!hasProductId) {
    return (
      <div className="panel connector-debug-page">
        <h2>KMS Connector Debug Details</h2>
        <div className="error-box"><strong>Missing product id.</strong> Open Details from a product row so the URL includes a productId query parameter.</div>
        <a className="details-link" href="/">← Back to search</a>
      </div>
    );
  }

  return (
    <div className="panel connector-debug-page">
      <h2>{sourceConfig.label} Connector Debug Details</h2>
      <div className="info-box">
        <div><strong>Product ID:</strong> {productId}</div>
        <div><strong>Connector:</strong> {sourceConfig.connectorName}</div>
        <div><strong>Source label:</strong> {sourceConfig.label} ({sourceConfig.sourceType})</div>
      </div>

      <h3>Product detail from database</h3>
      {productLoading && <div className="details-loader"><span className="spinner" /> Loading product details...</div>}
      {productError && <div className="error-box">{productError}</div>}
      {product && (
        <div className="details-grid">
          <div className="details-card">
            <div className="table-strong">Description</div>
            <div>{product.description || product.title || "N/A"}</div>
          </div>
          <div className="details-card">
            <div className="table-strong">Model / SKU</div>
            <div>{product.model_number || product.source_model_no || product.sku || product.source_product_key || "N/A"}</div>
          </div>
          <div className="details-card">
            <div className="table-strong">Connector query</div>
            <div>{connectorQuery || "N/A"}</div>
          </div>
        </div>
      )}

      <button
        className="details-btn"
        type="button"
        onClick={handleStart}
        disabled={productLoading || connectorLoading || !product || !connectorQuery}
      >
        start
      </button>

      <h3>Connector response</h3>
      {connectorLoading && <div className="details-loader"><span className="spinner" /> Running {sourceConfig.label} connector...</div>}
      {connectorError && <div className="error-box">{connectorError}</div>}
      {connectorResponse ? (
        <pre className="debug-json">{asPrettyJson(connectorResponse)}</pre>
      ) : (
        <div className="info-box">Click start to POST <code>{asPrettyJson({ query: connectorQuery })}</code> to <code>/search/{sourceConfig.connectorName}</code>.</div>
      )}

      {product && (
        <>
          <h3>Raw product detail</h3>
          <pre className="debug-json">{asPrettyJson(product)}</pre>
        </>
      )}
      <a className="details-link" href="/">← Back to search</a>
    </div>
  );
}
