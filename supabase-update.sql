-- Run this once in Supabase > SQL Editor if you created the docs table before lists, tasks and team existed.
alter table public.docs drop constraint if exists docs_collection_check;
alter table public.docs add constraint docs_collection_check
  check (collection in ('contacts', 'people', 'links', 'lists', 'tasks', 'team'));
