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
