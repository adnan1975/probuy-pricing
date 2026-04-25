const DEFAULT_TIMEOUT_MS = 8000;
const DEFAULT_RETRIES = 2;
const RETRYABLE_STATUS_CODES = new Set([408, 425, 429, 500, 502, 503, 504]);

export class ProductSearchClientError extends Error {
  constructor(message, { code, status, details, retriable = false } = {}) {
    super(message);
    this.name = "ProductSearchClientError";
    this.code = code || "UNKNOWN_ERROR";
    this.status = status;
    this.details = details;
    this.retriable = retriable;
  }
}

function getBaseUrl() {
  const envBase = import.meta.env.PROBUY_PRODUCT_SEARCH_API_BASE_URL;
  if (!envBase) {
    throw new ProductSearchClientError(
      "Missing PROBUY product search API base URL configuration",
      { code: "CONFIG_ERROR" }
    );
  }
  return envBase.replace(/\/$/, "");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function toArray(value) {
  if (Array.isArray(value)) return value;
  if (value === undefined || value === null || value === "") return [];
  return [value];
}

function appendValue(params, key, value) {
  if (value === undefined || value === null || value === "") {
    return;
  }
  if (Array.isArray(value)) {
    value.filter(Boolean).forEach((entry) => params.append(key, String(entry)));
    return;
  }
  params.append(key, String(value));
}

function appendRange(params, minKey, maxKey, range) {
  if (!range || typeof range !== "object") return;
  appendValue(params, minKey, range.min);
  appendValue(params, maxKey, range.max);
}

export function buildProductSearchParams(filters = {}) {
  const params = new URLSearchParams();
  appendValue(params, "q", filters.q);

  ["brand", "manufacturer", "category", "source", "stock_status"].forEach((textFilterKey) => {
    toArray(filters[textFilterKey]).forEach((value) => appendValue(params, textFilterKey, value));
  });

  const attributes = filters.attributes || {};
  Object.entries(attributes).forEach(([attributeKey, value]) => {
    toArray(value).forEach((entry) => appendValue(params, attributeKey, entry));
  });

  appendRange(params, "price_min", "price_max", filters.price);
  appendRange(params, "length_min", "length_max", filters.length);
  appendRange(params, "width_min", "width_max", filters.width);
  appendRange(params, "height_min", "height_max", filters.height);
  appendRange(params, "weight_min", "weight_max", filters.weight);
  appendValue(params, "limit", filters.limit);
  appendValue(params, "offset", filters.offset);

  return params;
}

function mapSearchResult(item) {
  if (!item || typeof item !== "object") {
    return null;
  }

  return {
    ...item,
    source: item.source || item.retailer || item.source_name || "Unknown",
    source_type: item.source_type || item.sourceType || "retail",
    title: item.title || item.name || "Untitled product",
    sku: item.sku || item.source_sku || item.part_number || "",
    brand: item.brand || item.manufacturer || "",
    availability: item.availability || item.stock_status || "",
    product_url: item.product_url || item.url || "",
    image_url: item.image_url || item.thumbnail_url || "",
    price_text: item.price_text || (typeof item.price_value === "number" ? `$${item.price_value.toFixed(2)}` : "")
  };
}

function mapSearchResponse(payload) {
  if (!payload || typeof payload !== "object") {
    throw new ProductSearchClientError("Invalid search payload shape", {
      code: "INVALID_PAYLOAD"
    });
  }

  if (!Array.isArray(payload.results)) {
    throw new ProductSearchClientError("Search payload missing results array", {
      code: "INVALID_PAYLOAD",
      details: payload
    });
  }

  return {
    results: payload.results.map(mapSearchResult).filter(Boolean),
    total_count: Number(payload.total_count || 0),
    facetDistribution: payload.facetDistribution && typeof payload.facetDistribution === "object"
      ? payload.facetDistribution
      : {},
    applied_filters: payload.applied_filters && typeof payload.applied_filters === "object"
      ? payload.applied_filters
      : {},
    engine_used: payload.engine_used || "unknown",
    fallback_applied: Boolean(payload.fallback_applied)
  };
}

async function fetchWithPolicy(pathname, { signal, timeoutMs = DEFAULT_TIMEOUT_MS, retries = DEFAULT_RETRIES, queryParams } = {}) {
  const baseUrl = getBaseUrl();
  const requestUrl = new URL(`${baseUrl}${pathname}`);
  if (queryParams instanceof URLSearchParams) {
    requestUrl.search = queryParams.toString();
  }

  let attempt = 0;
  while (attempt <= retries) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort("timeout"), timeoutMs);

    const onAbort = () => controller.abort(signal?.reason || "aborted");
    signal?.addEventListener("abort", onAbort, { once: true });

    try {
      const response = await fetch(requestUrl, {
        method: "GET",
        signal: controller.signal,
        headers: { Accept: "application/json" }
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const text = await response.text();
        const retriable = RETRYABLE_STATUS_CODES.has(response.status);
        if (retriable && attempt < retries) {
          attempt += 1;
          await sleep(250 * attempt);
          continue;
        }

        throw new ProductSearchClientError(`Product search API returned ${response.status}`, {
          code: response.status >= 500 ? "UPSTREAM_5XX" : "UPSTREAM_4XX",
          status: response.status,
          details: text,
          retriable
        });
      }

      try {
        return await response.json();
      } catch {
        throw new ProductSearchClientError("Invalid JSON payload from product search API", {
          code: "INVALID_PAYLOAD",
          status: response.status
        });
      }
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof ProductSearchClientError) {
        throw error;
      }
      const isAbort = error?.name === "AbortError";
      const isTimeout = isAbort && !signal?.aborted;
      if ((isAbort || error instanceof TypeError) && attempt < retries) {
        attempt += 1;
        await sleep(250 * attempt);
        continue;
      }

      if (isTimeout) {
        throw new ProductSearchClientError("Product search API request timed out", {
          code: "NETWORK_TIMEOUT",
          retriable: true
        });
      }

      throw new ProductSearchClientError("Network error calling product search API", {
        code: "NETWORK_ERROR",
        details: error?.message || String(error),
        retriable: true
      });
    } finally {
      signal?.removeEventListener("abort", onAbort);
    }
  }

  throw new ProductSearchClientError("Exhausted retries calling product search API", {
    code: "RETRY_EXHAUSTED",
    retriable: true
  });
}

export async function searchProducts(filters, options = {}) {
  const payload = await fetchWithPolicy("/api/search/products", {
    ...options,
    queryParams: buildProductSearchParams(filters)
  });
  return mapSearchResponse(payload);
}

export function getProductBySourceId(sourceProductId, options = {}) {
  return fetchWithPolicy(`/api/products/${encodeURIComponent(sourceProductId)}`, options);
}

export function getProductAttributes(sourceProductId, options = {}) {
  return fetchWithPolicy(`/api/products/${encodeURIComponent(sourceProductId)}/attributes`, options);
}

export function getSearchHealth(options = {}) {
  return fetchWithPolicy("/api/search/health", options);
}
