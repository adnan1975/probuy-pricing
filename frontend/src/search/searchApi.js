import { buildDetailRequestBody } from "./queryBuilder";
import { searchProducts } from "../integrations/probuyProductSearch";

/**
 * @param {{query: string, page: number, pageSize: number, filters?: Record<string, unknown>, signal?: AbortSignal}} args
 */
export async function fetchStep1Results({ query, page, pageSize, filters = {}, signal }) {
  const offset = Math.max(page - 1, 0) * pageSize;
  const payload = await searchProducts(
    {
      q: query,
      ...filters,
      limit: pageSize,
      offset
    },
    { signal }
  );

  return {
    results: payload.results,
    total_results: payload.total_count,
    total_pages: payload.total_count > 0 ? Math.ceil(payload.total_count / pageSize) : 0,
    facetDistribution: payload.facetDistribution,
    applied_filters: payload.applied_filters,
    engine_used: payload.engine_used,
    fallback_applied: payload.fallback_applied,
    analysis: {
      total_results: payload.total_count,
      priced_results: payload.results.filter((item) => typeof item.price_value === "number").length
    }
  };
}

/**
 * @param {{apiUrl: string, endpoint: string, query: string}} args
 */
export async function fetchDetailResults({ apiUrl, endpoint, query }) {
  const response = await fetch(`${apiUrl}/search/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: buildDetailRequestBody({ query })
  });

  const payload = response.ok ? await response.json() : null;
  const connectorResults = Array.isArray(payload?.results) ? payload.results : [];
  const priced = connectorResults.find((item) => typeof item.price_value === "number") || null;
  const connectorError = payload?.error || (!response.ok ? `Backend returned ${response.status}` : null);

  return {
    offer: priced,
    error: connectorError
  };
}

export async function startAutomatedPricing({ apiUrl, limit = 100 }) {
  const response = await fetch(`${apiUrl}/automated-pricing/start?limit=${limit}`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status} starting automated pricing`);
  }
  return response.json();
}

export async function fetchAutomatedPricingStatus({ apiUrl, jobId, signal }) {
  const response = await fetch(`${apiUrl}/automated-pricing/${jobId}`, { signal });
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status} fetching automated pricing status`);
  }
  return response.json();
}

export function openAutomatedPricingStream({ apiUrl, jobId }) {
  return new EventSource(`${apiUrl}/automated-pricing/${jobId}/stream`);
}
