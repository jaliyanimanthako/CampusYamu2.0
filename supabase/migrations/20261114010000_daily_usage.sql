-- Daily limits (campusyamu.api.limits): how many paid calls each student made per day
-- (action: chat | ai_recommendations | research; day in Sri Lanka time). Run after 20261114000000_chat_memory.sql.
-- Apply: Supabase dashboard -> SQL Editor -> paste and run.

create table if not exists public.daily_usage (
    user_id uuid not null references auth.users (id) on delete cascade,
    day date not null,
    action text not null,
    used integer not null default 0,
    primary key (user_id, day, action)
);

alter table public.daily_usage enable row level security;
