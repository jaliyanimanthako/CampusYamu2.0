-- Each student's latest search (campusyamu.memory.store): the form they sent to POST /v1/recommendations
-- and the report it returned, so the web page and the app can show the results again after a reload or
-- on another device (GET /v1/me/results), and the chat can find a course by its UNI code.
-- One row per student; a new search replaces it. Run after 20261114010000_daily_usage.sql.
-- Apply: Supabase dashboard -> SQL Editor -> paste and run.

create table if not exists public.student_results (
    user_id uuid primary key references auth.users (id) on delete cascade,
    form jsonb not null,
    report jsonb not null,
    used_llm integer not null default 0,
    saved_at timestamptz not null default now()
);

alter table public.student_results enable row level security;
