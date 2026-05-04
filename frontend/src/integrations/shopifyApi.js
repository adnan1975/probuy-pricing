const DEFAULT_TIMEOUT_MS = 8000;

export class ShopifyApiClientError extends Error {
  constructor(message, { code, status, details } = {}) {
    super(message);
    this.name = "ShopifyApiClientError";
    this.code = code || "UNKNOWN_ERROR";
    this.status = status;
    this.details = details;
  }
}

function getApiBaseUrl() {
  const apiBase = import.meta.env.VITE_API_URL;
  if (!apiBase) {
    throw new ShopifyApiClientError("Missing VITE_API_URL configuration for Shopify API calls", {
      code: "CONFIG_ERROR"
    });
  }
  return apiBase.replace(/\/$/, "");
}

async function fetchShopify(pathname, { method = "GET", body, headers = {}, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const requestUrl = new URL(`${getApiBaseUrl()}${pathname}`);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort("timeout"), timeoutMs);
  const onAbort = () => controller.abort(signal?.reason || "aborted");
  signal?.addEventListener("abort", onAbort, { once: true });

  try {
    const response = await fetch(requestUrl, {
      method,
      signal: controller.signal,
      headers: { Accept: "application/json", ...headers },
      body
    });

    if (!response.ok) {
      const details = await response.text();
      throw new ShopifyApiClientError(`Shopify API returned ${response.status}`, {
        code: response.status >= 500 ? "UPSTREAM_5XX" : "UPSTREAM_4XX",
        status: response.status,
        details
      });
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ShopifyApiClientError) {
      throw error;
    }
    if (error?.name === "AbortError") {
      throw new ShopifyApiClientError("Shopify API request timed out", { code: "NETWORK_TIMEOUT" });
    }
    throw new ShopifyApiClientError("Network error calling Shopify API", {
      code: "NETWORK_ERROR",
      details: error?.message || String(error)
    });
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", onAbort);
  }
}

export async function publishProductToShopifyDraft(sourceProductId, options = {}) {
  if (!sourceProductId) {
    throw new ShopifyApiClientError("sourceProductId is required", { code: "INVALID_INPUT" });
  }

  return fetchShopify(`/api/channels/shopify/products/${encodeURIComponent(sourceProductId)}/publish`, {
    ...options,
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ publish: false, status: "DRAFT" })
  });
}

export function fetchProductPublicationStatus(sourceProductId, options = {}) {
  if (!sourceProductId) {
    throw new ShopifyApiClientError("sourceProductId is required", { code: "INVALID_INPUT" });
  }

  return fetchShopify(`/api/products/${encodeURIComponent(sourceProductId)}`, options);
}
