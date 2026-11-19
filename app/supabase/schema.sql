-- TexDex tables for Supabase (Postgres) with row-level security.
--
-- How to apply: Supabase dashboard -> SQL Editor -> New query -> paste this
-- whole file -> Run. Then fill the species and rarity tables with
--     python -m app.supabase.seed
-- The local SQLite file in app/store.py has the same shape, for tests and
-- offline development.
--
-- Row-level security (RLS) in one sentence: the database itself checks,
-- on every query, that the row belongs to the logged-in user (auth.uid()),
-- so a bug in our app code cannot show one user another user's data.
-- Our Flask server makes every query WITH the logged-in user's token, so
-- these rules apply to it too.

-- One profile row per Supabase Auth user. Supabase Auth keeps the password
-- (hashed); this table keeps what the app shows.
create table profiles (
    id           uuid primary key references auth.users (id) on delete cascade,
    username     text not null unique,
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
    photo_file text not null,          -- path inside the private "photos" bucket
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

-- Table permissions. Newer Supabase projects give the API no access to a
-- table until it is granted. Grants say which actions a role may try at all;
-- the row-level security policies below then decide which ROWS.
--   authenticated = a logged-in app user;  service_role = the secret key (seed script)
grant select, insert, update on profiles to authenticated;
grant select on species, rarity to authenticated;
grant select, insert on catches to authenticated;
grant select, insert, update on species, rarity to service_role;

alter table profiles enable row level security;
alter table species  enable row level security;
alter table rarity   enable row level security;
alter table catches  enable row level security;

-- Profiles: you can read and change only your own.
create policy "own profile: read"   on profiles for select to authenticated using (auth.uid() = id);
create policy "own profile: insert" on profiles for insert to authenticated with check (auth.uid() = id);
create policy "own profile: update" on profiles for update to authenticated using (auth.uid() = id);

-- Species and rarity: any logged-in user can read; nobody can write from the app.
create policy "species: read" on species for select to authenticated using (true);
create policy "rarity: read"  on rarity  for select to authenticated using (true);

-- Catches: you can read and add only your own. No update or delete policy,
-- so catches cannot be edited or removed from the app.
create policy "own catches: read"   on catches for select to authenticated using (auth.uid() = user_id);
create policy "own catches: insert" on catches for insert to authenticated with check (auth.uid() = user_id);

-- The shared map shows OTHER people's catches through this view. It runs
-- with the view owner's rights (security_invoker = false) so it can see past
-- the "own catches" rule, but it only exposes what a map pin needs: no user
-- id, no photo, and every point rounded to about 1 km. (Protected species
-- are already blurred to about 25 km in the table itself.) Your own pins
-- come from the catches table, which RLS limits to you.
create view shared_map_points with (security_invoker = false) as
    select species_id, tier, region, caught_at,
           round(latitude::numeric, 2)::float8  as latitude,
           round(longitude::numeric, 2)::float8 as longitude
    from catches
    where latitude is not null
      and user_id is distinct from auth.uid();
revoke all on shared_map_points from anon, public;
grant select on shared_map_points to authenticated;

-- Photos live in a private Storage bucket, one folder per user
-- ("<user id>/<random>.jpg"). You can upload to and read only your own folder.
insert into storage.buckets (id, name, public) values ('photos', 'photos', false)
    on conflict (id) do nothing;
create policy "own photos: read" on storage.objects for select to authenticated
    using (bucket_id = 'photos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "own photos: upload" on storage.objects for insert to authenticated
    with check (bucket_id = 'photos' and (storage.foldername(name))[1] = auth.uid()::text);
