/**
 * @typedef {"High"|"Medium"|"Low"} ConfidenceLevel
 *
 * @typedef {Object} ProductResult
 * @property {string} source
 * @property {"distributor"|"retail"} [source_type]
 * @property {string} [title]
 * @property {string} [sku]
 * @property {string} [brand]
 * @property {string} [manufacturer_model]
 * @property {string} [model]
 * @property {number} [distributor_cost]
 * @property {number} [price_value]
 * @property {string} [price_text]
 * @property {string} [availability]
 * @property {number} [suggested_price]
 * @property {string} [warehouse]
 * @property {string} [warehouse_location]
 * @property {string} [location]
 * @property {string} [product_url]
 * @property {ConfidenceLevel} [confidence]
 */

/** @type {string} */
export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

/** @type {string[]} */
export const expectedSources = [
  "SCN International",
  "KMS Tools",
  "Canada Welding Supply",
  "Canadian Tire",
  "Amazon.ca",
  "Home Depot"
];

/** @type {{source: string, endpoint: string}[]} */
export const detailConnectorConfigs = [
  { source: "KMS Tools", endpoint: "kms_tools" },
  { source: "Canada Welding Supply", endpoint: "canada_welding_supply" },
  { source: "Canadian Tire", endpoint: "canadian_tire" },
  { source: "Home Depot", endpoint: "home_depot" },
  { source: "Amazon.ca", endpoint: "amazon_ca" }
];

/** @type {number[]} */
export const PAGE_SIZE_OPTIONS = [10, 25, 50];

export const MIN_QUERY_LENGTH = 2;
