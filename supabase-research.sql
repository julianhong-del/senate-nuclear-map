-- Senate Nuclear Map — look-up requests + the "General Matter — person details" scheduled task
-- Paste this whole file into Supabase > SQL Editor > New query > Run. Safe to run more than once.
--
-- 1. Fixes "Could not save (HTTP 400)" when logging a meeting with someone new (the table did not
--    allow the "research" collection the app now writes).
-- 2. Lets the scheduled task read look-up requests and hand-added people with the public key, nothing else.
-- 3. Fires the scheduled task within seconds whenever ANYONE on the team adds a person or asks for a
--    look-up. Part 3 stays dormant until the task's API token is stored (see the end of this file);
--    the two-hourly schedule keeps working either way.

-- ---------------------------------------------------------------------------------------------
-- 1. Allow look-up requests
alter table public.docs drop constraint if exists docs_collection_check;
alter table public.docs add constraint docs_collection_check
  check (collection in ('contacts', 'people', 'links', 'lists', 'tasks', 'team', 'research'));

-- ---------------------------------------------------------------------------------------------
-- 2. Read-only access for the scheduled task (anon key): look-up requests and hand-added people only.
--    Notes, meetings, tasks, lists and team stay readable by signed-in accounts only.
--    The grant gives the public role the table privilege; the policy below then limits it to those two collections.
grant usage on schema public to anon;
grant select on public.docs to anon;
drop policy if exists "anon reads research requests" on public.docs;
create policy "anon reads research requests" on public.docs
  for select to anon using (collection in ('research', 'people'));

-- ---------------------------------------------------------------------------------------------
-- 3. Fire the scheduled task when a person is added or a look-up is requested.
create extension if not exists pg_net;

-- Log of fires, so one person never fires the task more than once every 15 minutes
-- (logging a meeting saves the person and then the request a second apart; that is one fire, not two).
create table if not exists public.claude_fires (
  fid         bigserial primary key,
  person_id   text not null,
  event       text not null,
  fired_at    timestamptz not null default now(),
  request_id  bigint
);
alter table public.claude_fires enable row level security;   -- no policies: only the trigger below writes it

create or replace function public.docs_fire_research() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  tok    text;
  evt    text;
  last   timestamptz;
  rid    bigint;
begin
  -- Which saves count: a new hand-added person, or a new / re-made look-up request.
  if new.collection = 'people' and tg_op = 'INSERT' then
    evt := 'person_added';
  elsif new.collection = 'research' and coalesce(new.data ->> 'status', '') = 'requested'
        and (tg_op = 'INSERT' or old.data ->> 'requested' is distinct from new.data ->> 'requested') then
    evt := 'lookup_requested';
  else
    return new;
  end if;

  -- The task's API token lives in Supabase Vault (never in this file or in the repository).
  select decrypted_secret into tok from vault.decrypted_secrets where name = 'claude_fire_token' limit 1;
  if tok is null then return new; end if;        -- not set up yet: the two-hourly schedule covers it

  -- At most one fire per person per 15 minutes.
  select max(fired_at) into last from public.claude_fires where person_id = new.id;
  if last is not null and last > now() - interval '15 minutes' then return new; end if;

  rid := net.http_post(
    url     := 'https://api.anthropic.com/v1/claude_code/routines/trig_01ELWx9s97oziZ1qb5ALxPiE/fire',
    headers := jsonb_build_object(
                 'Content-Type',      'application/json',
                 'Authorization',     'Bearer ' || tok,
                 'anthropic-beta',    'experimental-cc-routine-2026-04-01',
                 'anthropic-version', '2023-06-01'),
    body    := jsonb_build_object('text', jsonb_build_object(
                 'event',        evt,
                 'person_id',    new.id,
                 'name',         new.data ->> 'name',
                 'requested',    coalesce(new.data ->> 'requested', new.data ->> 'added'),
                 'requested_by', coalesce(new.data ->> 'requested_by', new.updated_by))::text),
    timeout_milliseconds := 8000
  );
  insert into public.claude_fires (person_id, event, request_id) values (new.id, evt, rid);
  return new;
exception when others then
  return new;                                      -- a webhook problem must never block a save
end $$;

drop trigger if exists docs_fire_research on public.docs;
create trigger docs_fire_research after insert or update on public.docs
  for each row execute function public.docs_fire_research();

-- ---------------------------------------------------------------------------------------------
-- ONE-TIME SETUP for part 3 (do this in the SQL editor, not in this file, so the token is never committed):
--
--   a. claude.ai/code/routines → "General Matter — person details" → menu next to the name → Edit
--      → in the Trigger row click "+" → API → Generate token → copy it (it is shown once).
--      The panel's Fire URL should match the one in net.http_post above; if it differs, edit it above and re-run.
--   b. Run:   select vault.create_secret('<paste the token here>', 'claude_fire_token');
--      To rotate later:  select vault.update_secret(id, '<new token>') from vault.secrets where name = 'claude_fire_token';
--
-- To check it is working after adding a person:
--   select person_id, event, fired_at from public.claude_fires order by fid desc limit 5;
--   select id, status_code, content::text from net._http_response order by id desc limit 5;   -- 200 = the task started
