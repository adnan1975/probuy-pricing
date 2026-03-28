create schema if not exists pricing;

create table if not exists pricing.scn_pricing (
  model text not null,
  description text not null,
  list_price numeric(12,2),
  distributor_cost numeric(12,2),
  unit text,
  manufacturer text not null default '',
  warehouse text not null default '',
  updated_at timestamptz not null default now()
);

alter table pricing.scn_pricing
  add column if not exists warehouse text;

update pricing.scn_pricing
set manufacturer = coalesce(manufacturer, ''),
    warehouse = coalesce(warehouse, '');

alter table pricing.scn_pricing
  alter column manufacturer set default '',
  alter column manufacturer set not null,
  alter column warehouse set default '',
  alter column warehouse set not null;

alter table pricing.scn_pricing drop constraint if exists scn_pricing_pkey;
alter table pricing.scn_pricing add primary key (model, manufacturer, warehouse);

create index if not exists idx_scn_pricing_description on pricing.scn_pricing using gin (to_tsvector('simple', description));
create index if not exists idx_scn_pricing_manufacturer on pricing.scn_pricing (manufacturer);

create or replace function pricing.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_scn_pricing_updated_at on pricing.scn_pricing;
create trigger trg_scn_pricing_updated_at
before update on pricing.scn_pricing
for each row execute function pricing.set_updated_at();

create table if not exists pricing.connector_prices (
  id bigserial primary key,
  search_query text,
  source text not null,
  source_type text not null default 'retail',
  sku text,
  title text not null,
  price numeric(12,2),
  price_text text,
  available text,
  location text,
  currency text not null default 'CAD',
  product_url text,
  image_url text,
  confidence text,
  why text,
  date_created timestamptz not null default now()
);

alter table pricing.connector_prices
  add column if not exists location text;

create index if not exists idx_connector_prices_query on pricing.connector_prices (search_query);
create index if not exists idx_connector_prices_source on pricing.connector_prices (source);
create index if not exists idx_connector_prices_sku on pricing.connector_prices (sku);
create index if not exists idx_connector_prices_location on pricing.connector_prices (location);
create index if not exists idx_connector_prices_date_created on pricing.connector_prices (date_created desc);
create index if not exists idx_connector_prices_title_fts on pricing.connector_prices using gin (to_tsvector('simple', title));
