create schema if not exists probuy;

create table if not exists probuy.channel_sync_logs (
  id uuid primary key default gen_random_uuid(),
  source_product_id uuid,
  channel_code text not null,
  action text not null,
  status text not null,
  request_payload jsonb,
  response_payload jsonb,
  error_message text,
  triggered_by_user_id uuid,
  created_at timestamptz default now()
);

create index if not exists idx_channel_sync_logs_source_product_id
on probuy.channel_sync_logs(source_product_id);

create index if not exists idx_channel_sync_logs_channel_code
on probuy.channel_sync_logs(channel_code);

create index if not exists idx_channel_sync_logs_created_at
on probuy.channel_sync_logs(created_at desc);

alter table if exists probuy.product_channel_publications
drop constraint if exists product_channel_publications_publication_status_check;

alter table if exists probuy.product_channel_publications
add constraint product_channel_publications_publication_status_check
check (
  publication_status in (
    'NOT_PUBLISHED',
    'QUEUED',
    'PUBLISHED',
    'UNPUBLISHED',
    'FAILED',
    'NEEDS_REVIEW'
  )
);
