# Shopify Publishing Requirements for ProBuy QuoteSense / Price Sense

## 1. Purpose

Implement Shopify publishing from the front end application so selected products from the probuy database can be pushed, updated, published, and synced with Shopify through the Shopify Admin GraphQL API.

The attached Shopify export file should be used as the field-mapping reference.

Export observed columns include:

- `Handle`
- `Title`
- `Body (HTML)`
- `Vendor`
- `Product Category`
- `Type`
- `Tags`
- `Published`
- `Variant SKU`
- `Variant Inventory Qty`
- `Variant Price`
- `Image Src`
- `Cost per item`
- `Status`
- Product metafields such as:
  - `Packaged Cube (Cu.Ft.) (product.metafields.custom.packaged_cube_cu_ft)`
  - `Packaged Height ft (product.metafields.custom.packaged_height_ft)`
  - `Packaged Length ft (product.metafields.custom.packaged_length_ft)`
  - `Packaged Weight (lbs.) (product.metafields.custom.packaged_weight_lbs)`
  - `Packaged Width ft (product.metafields.custom.packaged_width_ft)`

## 2. High-Level Goal

Build a generic sales-channel publication system where Shopify is the first supported channel.

The app should support this flow:

```text
User search for product
        ↓
User selects product or batch of products
        ↓
User clicks publish button on result card
        ↓
Backend builds Shopify payload
        ↓
Backend assigns proper shopify category based on mapping 
        ↓
mapping is configured in settings page. 
        ↓
Backend creates or updates product in Shopify
        ↓
user should be able to publish product again 
        ↓
Frontend displays publication status
        ↓
Dashboard gets updated

```

## 3. Existing Database Design

use existing design only change if needed to implement this feature

### 3.2 `probuy.product_channel_publications`


Add more `publication_status` values:

```text
NOT_PUBLISHED
QUEUED
PUBLISHED
UNPUBLISHED
FAILED
NEEDS_REVIEW
```

If the current database constraint does not include `NEEDS_REVIEW`, add it or omit the state from the UI.

## 4. Add Sync Log Table

Create a new table for debugging Shopify publishing and sync operations.

```sql
create table if not exists probuy.channel_sync_logs (
  id uuid primary key default gen_random_uuid(),
  source_product_id uuid,
  channel_code text not null,
  action text not null,
  status text not null,
  request_payload jsonb,
  response_payload jsonb,
  error_message text,
  created_at timestamptz default now()
);

create index if not exists idx_channel_sync_logs_source_product_id
on probuy.channel_sync_logs(source_product_id);

create index if not exists idx_channel_sync_logs_channel_code
on probuy.channel_sync_logs(channel_code);

create index if not exists idx_channel_sync_logs_created_at
on probuy.channel_sync_logs(created_at desc);
```

Actions should include:

```text
SHOPIFY_PRODUCT_SET
SHOPIFY_PUBLISH
SHOPIFY_INVENTORY_SYNC
SHOPIFY_PRICE_SYNC
SHOPIFY_PRODUCT_FETCH
SHOPIFY_PUBLICATION_FETCH
```

Statuses should include:

```text
SUCCESS
FAILED
SKIPPED
```

## 5. Environment Variables

anything needed for us to access shopify 

Rules:

- All Shopify API calls must happen from the backend.
- Use `SHOPIFY_DEFAULT_PRODUCT_STATUS=DRAFT` during first implementation.
- Only switch to `ACTIVE` after testing.

## 6. Required Shopify API Scopes

The custom Shopify app should have these Admin API scopes:

```text
read_products
write_products
read_inventory
write_inventory
read_publications
write_publications
read_files
write_files
```

Optional future scopes:

```text
read_locations
write_publications
```

## 7. Shopify API Approach

Use Shopify Admin GraphQL API.

Primary mutations:

1. `productSet`
   - Use to create or update products from the ProBuy product database.
   - Use this as the main product upsert operation.

2. `publishablePublish`
   - Use after product creation/update when the product should be published to the Online Store sales channel.

3. `inventorySetQuantities`
   - Use for inventory sync after product and variant are created.

Important API notes:

- `productSet` is intended for syncing external source data into Shopify.
- In Shopify API version `2026-04`, some mutations require idempotency keys. Implement idempotency support for write operations where required.
- Inventory sync should use absolute quantity setting only when ProBuy/SCN inventory is treated as the source of truth.
- For inventory compare-and-swap fields, either fetch the current quantity first or intentionally opt out where Shopify allows it. Log the decision clearly.

## 8. Backend Modules to Create

Create a dedicated Shopify integration layer.

Suggested file structure:

```text
backend/
  services/
    shopify/
      shopifyClient.ts
      shopifyProductMapper.ts
      shopifyProductService.ts
      shopifyInventoryService.ts
      shopifyPublicationService.ts
      shopifySyncLogService.ts
      shopifyTypes.ts
  routes/
    shopifyRoutes.ts
  migrations/
    xxxx_channel_sync_logs.sql
```

If the backend is Python instead of Node/TypeScript, use equivalent files:

```text
backend/
  services/shopify/client.py
  services/shopify/product_mapper.py
  services/shopify/product_service.py
  services/shopify/inventory_service.py
  services/shopify/publication_service.py
  services/shopify/sync_log_service.py
  routers/shopify_routes.py
```

## 9. Shopify Client Requirements

Implement a reusable GraphQL client.

### Function

```ts
shopifyGraphQL<T>(query: string, variables?: Record<string, any>, options?: {
  idempotencyKey?: string;
}): Promise<T>
```

### Requirements

- Build endpoint:

```text
https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json
```

- Add headers:

```text
Content-Type: application/json
X-Shopify-Access-Token: {SHOPIFY_ADMIN_ACCESS_TOKEN}
```

- Log:
  - operation name
  - duration
  - Shopify errors
  - user errors
  - HTTP status
- Do not log full access token.
- Mask sensitive headers.
- Return structured errors.
- Retry only safe transient failures:
  - HTTP 429
  - HTTP 500
  - HTTP 502
  - HTTP 503
  - HTTP 504
- Use exponential backoff with max 3 attempts.
- Respect Shopify rate limit/throttle data if present in GraphQL response extensions.

## 10. Product Mapping Requirements

Create a mapper that converts internal ProBuy product data into Shopify `ProductSetInput`.

### 10.1 Internal Source Data

The mapper should load:

- source product
- brand/manufacturer
- product title
- product description
- category fields
- attributes
- bullet points
- SKU/model number
- pricing
- inventory
- image URLs
- package dimensions
- package weight
- publication status

### 10.2 Handle Generation

Generate Shopify handle using this priority:

```text
1. Existing saved Shopify handle from sync_metadata, if present
2. Existing handle from previous Shopify export/reconciliation mapping, if available
3. "scn-" + normalized SKU + "-" + normalized title
4. normalized title + "-" + normalized SKU
```

Handle rules:

- Lowercase
- Replace spaces and invalid characters with hyphens
- Remove duplicate hyphens
- Trim leading/trailing hyphens
- Max length: 255 characters
- Must be stable; do not generate a different handle on every sync

Example:

```text
Input SKU: ABC 123
Input Title: Professional MIG Welding Gloves
Handle: scn-abc-123-professional-mig-welding-gloves
```

### 10.3 Title

Use:

```text
source_products.title
```

Fallback order:

```text
ProductTitle
English description
Manufacturer + Model
SKU
```

### 10.4 Description HTML

Generate Shopify `descriptionHtml` from:

- product title
- short description
- bullet points
- attributes
- packaging details

Example:

```html
<p>Professional MIG Welding Gloves.</p>
<ul>
  <li>Durable construction for industrial use</li>
  <li>Suitable for professional safety applications</li>
</ul>
<table>
  <tbody>
    <tr><td>Brand</td><td>Example Brand</td></tr>
    <tr><td>Model</td><td>ABC123</td></tr>
  </tbody>
</table>
```

Rules:

- Sanitize HTML.
- Do not include empty attributes.
- Do not include raw JSON.
- Do not include supplier-only internal notes.

### 10.5 Vendor

Use:

```text
brand/manufacturer if clean and available
```

Fallback:

```text
SHOPIFY_DEFAULT_VENDOR
```

For the attached export, `Vendor` appears to be a key field and may currently use `PROBUY INC.`.

### 10.6 Product Type

Map from internal category.

Priority:

```text
1. Existing Shopify category mapping configuration
2. SCN CategoryEnglish
3. SCN CategoryEnglishLevel1
4. Internal normalized category
5. "Industrial Supply"
```

### 10.7 Product Category

Shopify's product category should come from a configurable category mapping table.

Create table if not already present:

```sql
create table if not exists probuy.channel_category_mappings (
  id uuid primary key default gen_random_uuid(),
  channel_code text not null,
  source_category_level1 text,
  source_category_level2 text,
  source_category_level3 text,
  shopify_product_category text,
  shopify_product_type text,
  tags text[],
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_channel_category_mappings_channel_code
on probuy.channel_category_mappings(channel_code);
```

The mapper should use this table before falling back to raw source category.

### 10.8 Tags

Generate tags from:

- brand
- category
- subcategory
- source name, e.g. `SCN`
- selected attributes
- safety/product family terms

Rules:

- Remove duplicates
- Trim whitespace
- Avoid more than 250 tags
- Do not include internal-only tags unless useful in Shopify admin
- Do not include supplier cost in tags

### 10.9 Status

Initial implementation:

```text
DRAFT
```

After successful testing, allow:

```text
ACTIVE
```

Do not make products active by default unless `SHOPIFY_PUBLISH_BY_DEFAULT=true`.

### 10.10 Variants

Start with single-variant products.

Map:

| Shopify Variant Field | Internal Source |
|---|---|
| SKU | source SKU / SCN Prod / model |
| Price | calculated sell price |
| Compare At Price | optional MSRP/list price |
| Cost | distributor cost |
| Barcode | optional UPC/barcode |
| Requires Shipping | true |
| Taxable | true |
| Weight | packaged weight |
| Weight Unit | lb or kg |

If a product has no price, mark as `NEEDS_REVIEW` and do not publish.

If a product has no SKU, mark as `NEEDS_REVIEW` and do not publish.

### 10.11 Images

Use image URLs from internal image fields or object storage/CDN.

Mapping:

| Shopify Field | Internal Source |
|---|---|
| media/image src | image_main |
| alt text | product title + brand |
| additional media | image_b, image_c, etc. |

Rules:

- Only send public HTTPS URLs.
- Skip local file paths.
- Skip empty/broken image URLs.
- Log skipped images.
- If no images exist, allow product creation but mark `sync_metadata.has_images=false`.

### 10.12 Metafields

Map package fields to Shopify metafields:

| Internal Field | Shopify Namespace | Shopify Key | Shopify Type |
|---|---|---|---|
| packaged_cube_cu_ft | custom | packaged_cube_cu_ft | number_decimal |
| packaged_height_ft | custom | packaged_height_ft | number_decimal |
| packaged_length_ft | custom | packaged_length_ft | number_decimal |
| packaged_weight_lbs | custom | packaged_weight_lbs | number_decimal |
| packaged_width_ft | custom | packaged_width_ft | number_decimal |

Example:

```json
{
  "namespace": "custom",
  "key": "packaged_weight_lbs",
  "type": "number_decimal",
  "value": "1.25"
}
```

Rules:

- Do not send empty metafields.
- Convert all numeric values to strings for Shopify input.
- Validate numeric fields before sending.
- Avoid deleting existing Shopify metafields accidentally. If using `productSet` with metafields, confirm behavior and consider fetching/merging existing metafields before update.

## 11. Product Upsert Service

Create:

```ts
publishProductToShopify(sourceProductId: string, options?: {
  publish?: boolean;
  status?: "DRAFT" | "ACTIVE";
  forceUpdate?: boolean;
}): Promise<ShopifyPublishResult>
```

### Steps

1. Load source product and related data.
2. Validate required fields:
   - SKU
   - title
   - price
3. Load or create publication row for `SHOPIFY`.
4. Build Shopify product payload.
5. Determine if this is create or update:
   - If `external_product_id` exists, update using Shopify product ID.
   - Else if saved handle exists, upsert by handle/identifier.
   - Else create new.
6. Call `productSet`.
7. Parse product ID, handle, variant ID, inventory item ID.
8. Save returned IDs in `product_channel_publications`:
   - `external_product_id`
   - `external_variant_id`
   - `sync_metadata.shopify_handle`
   - `sync_metadata.inventory_item_id`
9. If `publish=true`, call publication service.
10. Update status:
   - `PUBLISHED` if published
   - `QUEUED` if queued
   - `FAILED` if Shopify error
   - `NEEDS_REVIEW` if validation failed
11. Insert sync log row.

### Result Object

```ts
type ShopifyPublishResult = {
  sourceProductId: string;
  success: boolean;
  status: "PUBLISHED" | "QUEUED" | "FAILED" | "NEEDS_REVIEW" | "UNPUBLISHED";
  shopifyProductId?: string;
  shopifyVariantId?: string;
  shopifyHandle?: string;
  errors?: Array<{ field?: string[] | string; message: string }>;
};
```

## 12. ProductSet GraphQL Mutation

Implement mutation similar to:

```graphql
mutation ProductSet($identifier: ProductSetIdentifiers, $input: ProductSetInput!, $synchronous: Boolean!) {
  productSet(identifier: $identifier, input: $input, synchronous: $synchronous) {
    product {
      id
      handle
      title
      status
      variants(first: 20) {
        nodes {
          id
          sku
          inventoryItem {
            id
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

Use `synchronous=true` for single product publishing.

For bulk publishing, consider asynchronous mode or a queue after Phase 1 is stable.

## 13. Publish to Online Store

Create service:

```ts
publishShopifyProduct(productGid: string): Promise<void>
```

Use `publishablePublish` with `SHOPIFY_ONLINE_STORE_PUBLICATION_ID`.

Mutation shape:

```graphql
mutation PublishProduct($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    publishable {
      ... on Product {
        id
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

Rules:

- Only call after successful `productSet`.
- Product should be `ACTIVE` before publishing.
- If product is `DRAFT`, do not publish unless explicitly requested and Shopify allows it.
- Store publication result in `product_channel_publications`.
- Update:
  - `is_published=true`
  - `publication_status='PUBLISHED'`
  - `published_at=now()`

## 14. Inventory Sync

Create:

```ts
syncShopifyInventory(sourceProductId: string): Promise<void>
```

Steps:

1. Load product publication row.
2. Read `inventory_item_id` from `sync_metadata`.
3. Load available inventory from internal inventory table.
4. Resolve Shopify location ID from env.
5. Call `inventorySetQuantities`.
6. Log result.
7. Update `last_sync_at`.

Rules:

- If no inventory item ID exists, fetch product variant from Shopify and store it.
- If no inventory data exists, skip and log `SKIPPED`.
- Do not set inventory to 0 unless source data explicitly says 0.
- Use absolute quantity only if SCN/ProBuy is the source of truth.

## 15. Price Sync

Create:

```ts
syncShopifyPrice(sourceProductId: string): Promise<void>
```

Simplest implementation:

- Use `productSet` again with the same product identifier and updated variant price/cost.

Rules:

- Validate sell price before update.
- Do not publish products with missing or zero invalid price.
- Save price in sync metadata:

```json
{
  "last_price_synced": "24.99",
  "last_cost_synced": "12.50",
  "last_price_sync_at": "2026-05-03T00:00:00Z"
}
```

## 16. API Endpoints

Add backend routes.

### 16.1 Publish One Product

```http
POST /api/channels/shopify/products/:sourceProductId/publish
```

Body:

```json
{
  "publish": false,
  "status": "DRAFT",
  "forceUpdate": false
}
```

Response:

```json
{
  "success": true,
  "sourceProductId": "uuid",
  "status": "QUEUED",
  "shopifyProductId": "gid://shopify/Product/123",
  "shopifyVariantId": "gid://shopify/ProductVariant/456",
  "shopifyHandle": "scn-abc-123-product-title"
}
```

### 16.2 Bulk Publish

```http
POST /api/channels/shopify/products/publish-bulk
```

Body:

```json
{
  "sourceProductIds": ["uuid1", "uuid2"],
  "publish": false,
  "status": "DRAFT"
}
```

Rules:

- Process in small batches.
- Do not crash the whole batch if one product fails.
- Return per-product result.
- Add queue support if available.

### 16.3 Sync Inventory

```http
POST /api/channels/shopify/products/:sourceProductId/sync-inventory
```

### 16.4 Sync Price

```http
POST /api/channels/shopify/products/:sourceProductId/sync-price
```

### 16.5 Get Shopify Status

```http
GET /api/channels/shopify/products/:sourceProductId/status
```

Response should include:

```json
{
  "sourceProductId": "uuid",
  "publicationStatus": "PUBLISHED",
  "isPublished": true,
  "shopifyProductId": "gid://shopify/Product/123",
  "shopifyVariantId": "gid://shopify/ProductVariant/456",
  "shopifyHandle": "scn-abc-product",
  "lastSyncAt": "2026-05-03T00:00:00Z",
  "lastError": null
}
```

### 16.6 Get Sync Logs

```http
GET /api/channels/shopify/products/:sourceProductId/logs
```

Return recent sync logs for debugging.

## 17. Frontend Requirements

Update the product search/product detail UI.

### 17.1 Product Card Status

Display Shopify status:

```text
Shopify: Not Published
Shopify: Draft Created
Shopify: Published
Shopify: Failed
Shopify: Needs Review
```

### 17.2 Product Card Buttons

Show context-aware buttons:

If not published:

```text
Push to Shopify
```

If draft exists:

```text
Update Shopify Draft
Publish to Shopify
```

If published:

```text
View in Shopify
Sync Price
Sync Inventory
Unpublish
```

If failed:

```text
Retry
View Error
```

### 17.3 Filters

Add search filters:

```text
Shopify Status:
- All
- Not Published
- Published
- Failed
- Needs Review
```

Backend should filter using `probuy.product_channel_publications`.

### 17.4 Bulk Actions

Add:

```text
Select products
Bulk Push to Shopify as Draft
Bulk Publish to Shopify
Bulk Sync Price
Bulk Sync Inventory
```

Bulk actions can be Phase 2 if needed.

## 18. Reconciliation with Shopify Export

Use the attached Shopify export to implement a one-time reconciliation script.

Script name:

```text
scripts/reconcile_shopify_export.py
```

or:

```text
scripts/reconcileShopifyExport.ts
```

Purpose:

- Read Shopify export CSV.
- Match rows to internal products by:
  - `Variant SKU`
  - handle
  - title fallback
- Update `product_channel_publications`.
- Save:
  - handle
  - status
  - vendor
  - product category
  - product type
  - tags
  - image URL
- Produce CSV of not-found Shopify products.
- Produce CSV of internal products not found in Shopify.

Required outputs:

```text
output/shopify_reconciliation_matched.csv
output/shopify_reconciliation_shopify_not_found_in_source.csv
output/shopify_reconciliation_source_not_found_in_shopify.csv
```

## 19. Error Handling

Validation failures should not call Shopify.

Mark as `NEEDS_REVIEW` if:

- missing SKU
- missing title
- missing price
- invalid price
- invalid image URL
- invalid category mapping if category is required
- dangerous or unsupported product type if business rules require exclusion

Mark as `FAILED` if:

- Shopify API returns user errors
- HTTP failure after retries
- GraphQL error
- publication fails

Store error in:

```text
product_channel_publications.last_error
channel_sync_logs.error_message
channel_sync_logs.response_payload
```

## 20. Idempotency

Implement idempotency for Shopify write operations.

Suggested key format:

```text
shopify:{action}:{sourceProductId}:{payloadHash}
```

Examples:

```text
shopify:productSet:8f8a...:a12b34
shopify:publish:8f8a...:a12b34
shopify:inventorySetQuantities:8f8a...:a12b34
```

Store payload hash in `sync_metadata`.

## 21. Security Requirements

- Shopify token must be backend-only.
- Do not commit `.env` files.
- Mask token in logs.
- Add authorization to Shopify publishing endpoints.
- Only admin users should publish products.
- Log user ID who triggered publish if auth is available.

Optional field for sync logs:

```sql
alter table probuy.channel_sync_logs
add column if not exists triggered_by_user_id uuid;
```

## 22. Testing Requirements

### 22.1 Unit Tests

Test:

- handle generation
- title fallback
- description HTML generation
- tag generation
- price validation
- metafield mapping
- image URL filtering
- Shopify payload generation
- publication status transitions

### 22.2 Integration Tests

Mock Shopify GraphQL and test:

- successful product creation
- Shopify user error
- HTTP 429 retry
- failed inventory sync
- failed publish after successful productSet
- existing publication row update

### 22.3 Manual Test Cases

1. Push one valid product as draft.
2. Confirm product appears in Shopify admin.
3. Confirm variant SKU and price are correct.
4. Confirm cost is saved.
5. Confirm package metafields are saved.
6. Confirm image appears.
7. Publish product to Online Store.
8. Confirm app status changes to `PUBLISHED`.
9. Update price in QuoteSense and sync again.
10. Update inventory and sync again.
11. Try product with missing price and confirm `NEEDS_REVIEW`.
12. Try invalid image URL and confirm product still pushes but image is skipped/logged.

## 23. Phase Plan

### Phase 1: Single Product Draft Push

Deliver:

- Shopify client
- mapper
- productSet mutation
- publication table update
- sync log table
- frontend button: `Push to Shopify as Draft`

### Phase 2: Publish to Online Store

Deliver:

- publication ID config
- `publishablePublish`
- status update to `PUBLISHED`
- frontend button: `Publish`

### Phase 3: Price and Inventory Sync

Deliver:

- price sync
- inventory sync
- status/log updates
- frontend buttons

### Phase 4: Shopify Export Reconciliation

Deliver:

- import Shopify export CSV
- match by SKU/handle
- update publication records
- generate not-found reports

### Phase 5: Bulk Publishing

Deliver:

- bulk endpoint
- frontend multi-select
- per-product result
- queue support if available

### Phase 6: Category Mapping UI

Deliver:

- category mapping table
- frontend settings page
- mapper uses saved mapping before fallback

## 24. Acceptance Criteria

Implementation is complete when:

- Admin can push one internal product to Shopify as draft.
- Shopify product is created with correct title, handle, SKU, price, cost, vendor, type, tags, image, and package metafields.
- App stores Shopify product ID and variant ID.
- App displays Shopify publication status.
- Admin can publish product to Online Store.
- Admin can sync price.
- Admin can sync inventory.
- Failed pushes are logged with readable error messages.
- Products with missing required data are marked `NEEDS_REVIEW` and are not sent to Shopify.
- Shopify token is not exposed to frontend.
- Reconciliation script can read a Shopify export and update publication records.

## 25. Do Not Implement Yet

Do not implement these until the basic flow is stable:

- Full multi-variant product support
- Shopify Markets-specific publishing
- Automated nightly sync
- Shopify webhook ingestion
- Image upload/staged upload pipeline
- AI-generated descriptions
- Complex product bundle support
- Automatic category prediction

## 26. Developer Notes

Use the Shopify export as a mapping reference, not as the main long-term publishing mechanism.

The long-term source of truth should be:

```text
ProBuy / QuoteSense DB → Shopify API
```

Not:

```text
CSV → manual Shopify import
```

CSV should only be used for:

- initial reconciliation
- debugging
- manual backup
- emergency bulk import

## 27. Suggested First Codex Task

Implement Phase 1 only:

```text
Create Shopify Admin GraphQL integration for publishing a single ProBuy source product as a Shopify draft using productSet. Add backend service, mapper, route, sync log table, and update product_channel_publications with Shopify product ID, variant ID, handle, last sync time, and status. Do not implement bulk publishing yet.
```
