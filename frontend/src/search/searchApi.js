import { buildDetailRequestBody, buildStep1QueryParams } from "./queryBuilder";

/**
 * @param {{apiUrl: string, query: string, page: number, pageSize: number, signal?: AbortSignal}} args
 */
export async function fetchStep1Results({ apiUrl, query, page, pageSize, signal }) {
  const params = buildStep1QueryParams({ product: query, page, pageSize });
  const response = await fetch(`${apiUrl}/search/step1?${params.toString()}`, { signal });
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status} from step1`);
  }
  return response.json();
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
