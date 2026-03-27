create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.listings (
  id bigint generated always as identity primary key,
  source_kind text not null check (source_kind in ('hotel', 'kvartira')),
  source_channel text not null,
  source_message_id bigint not null,
  source_topic_id bigint,
  slug text not null unique,
  title text not null,
  summary text,
  excerpt text,
  city text,
  location_text text,
  distance_text text,
  beach_text text,
  capacity_text text,
  page_url text,
  telegram_url text,
  published_at date,
  has_video boolean not null default false,
  cover_url text,
  is_active boolean not null default true,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_kind, source_channel, source_message_id)
);

create table if not exists public.listing_media (
  id bigint generated always as identity primary key,
  listing_id bigint not null references public.listings(id) on delete cascade,
  media_role text not null check (media_role in ('card', 'gallery', 'video', 'cover')),
  sort_order integer not null default 0,
  mime_type text,
  source_url text,
  storage_bucket text,
  storage_path text,
  public_url text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (listing_id, media_role, sort_order)
);

create index if not exists idx_listings_source_kind on public.listings(source_kind);
create index if not exists idx_listings_published_at on public.listings(published_at desc nulls last);
create index if not exists idx_listings_active_kind on public.listings(is_active, source_kind);
create index if not exists idx_listing_media_listing_id on public.listing_media(listing_id);

drop trigger if exists trg_listings_updated_at on public.listings;
create trigger trg_listings_updated_at
before update on public.listings
for each row
execute function public.set_updated_at();

drop trigger if exists trg_listing_media_updated_at on public.listing_media;
create trigger trg_listing_media_updated_at
before update on public.listing_media
for each row
execute function public.set_updated_at();

alter table public.listings enable row level security;
alter table public.listing_media enable row level security;

drop policy if exists "Public can read active listings" on public.listings;
create policy "Public can read active listings"
on public.listings
for select
using (is_active = true);

drop policy if exists "Public can read listing media" on public.listing_media;
create policy "Public can read listing media"
on public.listing_media
for select
using (true);

insert into storage.buckets (id, name, public)
values ('site-media', 'site-media', true)
on conflict (id) do update
set public = excluded.public;

drop policy if exists "Public can read site media" on storage.objects;
create policy "Public can read site media"
on storage.objects
for select
using (bucket_id = 'site-media');
