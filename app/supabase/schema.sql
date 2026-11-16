-- TexDex tables for Supabase (Postgres) with row-level security.
--
-- NOT YET APPLIED ANYWHERE. This is the plan for when the Supabase project
-- exists; today the app runs on the local SQLite file in app/store.py, which
-- has the same tables. Run this in the Supabase SQL editor during setup.
--
-- Row-level security (RLS) in one sentence: the database itself checks,
-- on every query, that the row belongs to the logged-in user (auth.uid()),
-- so a bug in our app code cannot show one user another user's data.

-- One profile row per Supabase Auth user.
create table profiles (
    id           uuid primary key references auth.users (id) on delete cascade,
    display_name text not null,
    avatar       text not null default '🤠',
    created_at   timestamptz not null default now()
);

-- Reference data from Person A's CSVs (docs/interface.md). Read-only for users.
create table species (
    species_id      text primary key,
    scientific_name text not null,
    common_name     text not null,
    family          text not null,
    protected       boolean not null,
    venomous        boolean not null
);

create table rarity (
    species_id  text not null references species (species_id),
    region      text not null,
    season      text not null check (season in ('spring', 'summer', 'fall', 'winter')),
    rarity_tier text not null check (rarity_tier in ('common', 'uncommon', 'rare', 'very_rare')),
    primary key (species_id, region, season)
);

-- One row per confirmed catch. The collection ("My Dex") is computed from
-- this table; there is no separate collection table to drift out of step.
-- latitude/longitude hold the ALREADY BLURRED point for protected species:
-- the app blurs before inserting (app/privacy.py), so the exact location of
-- a protected animal never reaches the database.
create table catches (
    id         bigint generated always as identity primary key,
    user_id    uuid not null references profiles (id) on delete cascade,
    species_id text not null references species (species_id),
    photo_path text not null,
    photo_hash text not null,
    latitude   double precision,
    longitude  double precision,
    region     text not null default '',
    tier       text not null,
    confidence real not null,
    xp         integer not null,
    caught_at  timestamptz not null default now(),
    unique (user_id, photo_hash)   -- the duplicate-photo check, enforced by the database
);

alter table profiles enable row level security;
alter table species  enable row level security;
alter table rarity   enable row level security;
alter table catches  enable row level security;

-- Profiles: you can read and change only your own.
create policy "own profile: read"   on profiles for select using (auth.uid() = id);
create policy "own profile: insert" on profiles for insert with check (auth.uid() = id);
create policy "own profile: update" on profiles for update using (auth.uid() = id);

-- Species and rarity: any logged-in user can read; nobody can write from the app.
create policy "species: read" on species for select to authenticated using (true);
create policy "rarity: read"  on rarity  for select to authenticated using (true);

-- Catches: you can read and add only your own. No update or delete policy,
-- so catches cannot be edited or removed from the app.
create policy "own catches: read"   on catches for select using (auth.uid() = user_id);
create policy "own catches: insert" on catches for insert with check (auth.uid() = user_id);

-- The shared map reads through this view, which exposes no user ids and
-- rounds every point to about 1 km. (Protected species are already blurred
-- to about 25 km in the table itself.)
create view shared_map_points with (security_invoker = false) as
    select species_id, tier, round(latitude::numeric, 2) as latitude,
           round(longitude::numeric, 2) as longitude
    from catches
    where latitude is not null;
grant select on shared_map_points to authenticated;
