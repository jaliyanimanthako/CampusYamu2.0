-- Course chat memory (campusyamu.memory.store). One conversation per student per course offering,
-- its messages, and the student's lasting facts. Deleting the auth user deletes all of it (cascade).
--
-- Apply: Supabase dashboard -> SQL Editor -> paste and run, or `supabase db push` with the Supabase CLI.
-- The API connects as the server (SUPABASE_DB_URL), which bypasses Row Level Security. RLS is switched on
-- with no policies, so the publishable (anon) key in the apps can never read these tables directly:
-- clients only see memory through the API.

create table if not exists public.chat_conversations (
    id uuid primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    uni_code text not null,
    course_code text not null default '',
    course_name text not null default '',
    university text not null default '',
    summary text not null default '',
    summarized_through integer not null default 0,   -- messages up to this seq are in the summary
    facts_through integer not null default 0,        -- messages up to this seq were read for facts
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, uni_code)
);

create table if not exists public.chat_messages (
    id uuid primary key,
    conversation_id uuid not null references public.chat_conversations (id) on delete cascade,
    seq integer not null,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    sources jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    unique (conversation_id, seq)
);

create table if not exists public.student_facts (
    id uuid primary key,
    user_id uuid not null references auth.users (id) on delete cascade,
    fact text not null,
    category text not null,
    source_uni_code text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists chat_conversations_user on public.chat_conversations (user_id, updated_at desc);
create index if not exists student_facts_user on public.student_facts (user_id);

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;
alter table public.student_facts enable row level security;
