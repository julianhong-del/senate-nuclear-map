-- Senate Nuclear Map — team storage
-- Paste this whole file into Supabase > SQL Editor > New query > Run.
-- One generic table holds every record the app writes (contacts, added people, referral links).

create table if not exists public.docs (
  collection  text not null check (collection in ('contacts', 'people', 'links', 'lists', 'tasks', 'team')),
  id          text not null,
  data        jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now(),
  updated_by  text,
  primary key (collection, id)
);

-- Row-level security: nobody reads or writes unless a policy says so.
alter table public.docs enable row level security;

-- Only signed-in users (the accounts you create) can read and write. The anon key alone gets nothing.
drop policy if exists "team read"   on public.docs;
drop policy if exists "team insert" on public.docs;
drop policy if exists "team update" on public.docs;
drop policy if exists "team delete" on public.docs;
create policy "team read"   on public.docs for select to authenticated using (true);
create policy "team insert" on public.docs for insert to authenticated with check (true);
create policy "team update" on public.docs for update to authenticated using (true) with check (true);
create policy "team delete" on public.docs for delete to authenticated using (true);

-- Stamp who changed what, from the signed-in user's JWT (cannot be spoofed by the browser).
create or replace function public.docs_stamp() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  new.updated_at := now();
  new.updated_by := coalesce(auth.jwt() ->> 'email', new.updated_by);
  return new;
end $$;
drop trigger if exists docs_stamp on public.docs;
create trigger docs_stamp before insert or update on public.docs
  for each row execute function public.docs_stamp();

-- Optional: keep a change history so an accidental overwrite can be recovered.
create table if not exists public.docs_history (
  hid         bigserial primary key,
  collection  text not null,
  id          text not null,
  data        jsonb,
  changed_at  timestamptz not null default now(),
  changed_by  text,
  op          text not null
);
alter table public.docs_history enable row level security;
create policy "history read" on public.docs_history for select to authenticated using (true);
create or replace function public.docs_history_fn() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'DELETE' then
    insert into public.docs_history (collection, id, data, changed_by, op) values (old.collection, old.id, old.data, auth.jwt() ->> 'email', 'delete');
    return old;
  else
    insert into public.docs_history (collection, id, data, changed_by, op) values (new.collection, new.id, new.data, auth.jwt() ->> 'email', lower(tg_op));
    return new;
  end if;
end $$;
drop trigger if exists docs_history_trg on public.docs;
create trigger docs_history_trg after insert or update or delete on public.docs
  for each row execute function public.docs_history_fn();
