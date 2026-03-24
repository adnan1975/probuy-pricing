create schema if not exists pricing;

create table if not exists pricing.scn_pricing (
  model text primary key,
  description text not null,
  list_price numeric(12,2),
  distributor_cost numeric(12,2),
  unit text,
  manufacturer text,
  updated_at timestamptz not null default now()
);

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
