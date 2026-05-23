create table if not exists ci_builds (
  message_id    text primary key,
  vendor        text not null,
  build_id      text not null,
  status        text not null,
  fields        jsonb not null,
  received_at   timestamptz not null,
  created_at    timestamptz not null default now()
);

create index if not exists ci_builds_repo_idx
  on ci_builds ((fields->>'repo'));
create index if not exists ci_builds_vendor_received_idx
  on ci_builds (vendor, received_at desc);
create index if not exists ci_builds_status_idx
  on ci_builds (status);
