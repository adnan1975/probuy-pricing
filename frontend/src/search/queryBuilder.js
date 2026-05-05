/**
 * @param {{product: string, page: number, pageSize: number}} params
 * @returns {URLSearchParams}
 */
export function buildStep1QueryParams({ product, page, pageSize }) {
  return new URLSearchParams({
    product,
    page: String(page),
    page_size: String(pageSize)
  });
}

/**
 * @param {{query: string}} body
 * @returns {string}
 */
export function buildDetailRequestBody(body) {
  return JSON.stringify(body);
}
