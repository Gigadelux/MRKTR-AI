-- mrktr AI: Supabase (Postgres + pgvector) schema
-- Last updated: 2026-11-20
--
-- Run once in the Supabase SQL editor (use the DEV project first).
-- Safe to re-run: every statement is idempotent. Documentation: SCHEMA.md.
--
-- Access model: row-level security is ON for every table and no policies are
-- defined, so the anon and authenticated roles can read nothing. The backend
-- uses the service-role key, which bypasses RLS. masked_messages holds raw
-- attack text and must never be exposed to any other role.

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- users: one row per person in the funnel
-- ---------------------------------------------------------------------------
create table if not exists users (
    user_id       uuid primary key default gen_random_uuid(),
    channel_ids   jsonb not null default '{}'::jsonb,   -- e.g. {"telegram": 123456789}
    email         text,
    start_token   text unique,                          -- single-use token in the t.me deep link
    pref_mode     text check (pref_mode in ('audio_transcript', 'audio_only', 'text_only')),
    consent_at    timestamptz,                          -- null = no consent on record: the bot must not reply
    company       text not null,                        -- company profile this lead belongs to
    created_at    timestamptz not null default now()
);
comment on table users is 'People in the outreach funnel. Deleting a row deletes everything linked to it.';
comment on column users.channel_ids is 'External ids per channel, e.g. {"telegram": 123456789}.';
create unique index if not exists users_telegram_id_uq
    on users ((channel_ids ->> 'telegram')) where channel_ids ->> 'telegram' is not null;
comment on column users.start_token is 'Token in the Telegram deep link; redeeming it links the email to the Telegram user.';
comment on column users.pref_mode is 'Hard limit on what the agent may send. text_only means voice notes are refused.';
comment on column users.consent_at is 'When the user gave consent. Null means the bot must not reply.';
comment on column users.company is 'Name of the company profile (folder under gitignore/data/).';

-- ---------------------------------------------------------------------------
-- crm: qualification data the agent writes
-- ---------------------------------------------------------------------------
create table if not exists crm (
    user_id       uuid primary key references users (user_id) on delete cascade,
    company_name  text,
    company_description text,
    role          text,
    industry      text,
    size          text,
    use_case      text,
    budget        text,
    timeline      text,
    status        text not null default 'new'
                  check (status in ('new', 'contacted', 'engaged', 'qualified', 'booked', 'not_now', 'unsubscribed')),
    updated_at    timestamptz not null default now()
);
-- for databases created before company_description existed (no-op otherwise)
alter table crm add column if not exists company_description text;
comment on table crm is 'Lead qualification fields, written through the update_crm tool.';
comment on column crm.company_name is 'The lead''s own company (not the company running the agent).';
comment on column crm.company_description is 'Short description of what the lead''s company does, as learned in conversation.';
comment on column crm.status is 'Funnel stage of the lead.';

-- ---------------------------------------------------------------------------
-- messages: every message, with a transcript for audio
-- ---------------------------------------------------------------------------
create table if not exists messages (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null references users (user_id) on delete cascade,
    channel             text not null check (channel in ('email', 'telegram')),
    channel_message_id  text,
    direction           text not null check (direction in ('in', 'out')),
    text                text,
    audio_ref           text,                           -- Telegram file_id or a path under gitignore/temp/
    transcript_source   text not null
                        check (transcript_source in ('user_text', 'stt', 'agent_text', 'tts_script')),
    metadata            jsonb not null default '{}'::jsonb,
    created_at          timestamptz not null default now()
);
-- databases created before this column existed
alter table messages add column if not exists metadata jsonb not null default '{}'::jsonb;
-- Telegram message ids are unique only inside one chat, so uniqueness is per user, not per channel.
drop index if exists messages_channel_msg_uq;
create unique index if not exists messages_user_channel_msg_uq
    on messages (user_id, channel, channel_message_id) where channel_message_id is not null;
create index if not exists messages_user_created_idx on messages (user_id, created_at);
comment on table messages is 'Every incoming and outgoing message. Audio always has a transcript in text.';
comment on column messages.direction is 'in = from the user, out = from the agent.';
comment on column messages.audio_ref is 'Reference to the audio file, if the message was a voice note.';
comment on column messages.metadata is 'Channel details and measured usage. Email: gmail_thread_id, rfc822_message_id, subject. Voice: duration_s, mime_type. Usage: llm_input_tokens, llm_output_tokens, tts_characters, stt_seconds. Measured values only.';
comment on column messages.transcript_source is 'user_text = typed; stt = speech-to-text of a user voice note; agent_text = agent text; tts_script = script sent to text-to-speech.';

-- ---------------------------------------------------------------------------
-- masked_messages: originals of sentences removed before the LLM saw them
-- ---------------------------------------------------------------------------
create table if not exists masked_messages (
    id             uuid primary key default gen_random_uuid(),
    message_id     uuid not null references messages (id) on delete cascade,
    original_text  text not null,                       -- raw attack text: stored ONLY here
    masked_text    text not null,                       -- what the LLM saw, e.g. "[removed: possible prompt injection]"
    detector       text not null,                       -- e.g. prompt_guard, llama_guard
    score          double precision,
    reason         text,
    created_at     timestamptz not null default now()
);
create index if not exists masked_messages_message_idx on masked_messages (message_id);
comment on table masked_messages is 'Sentences replaced before the LLM saw them. Owner only: service role access.';
comment on column masked_messages.original_text is 'Raw flagged sentence. Never log or store it anywhere else.';
comment on column masked_messages.detector is 'Which guard flagged it.';
comment on column masked_messages.score is 'Guard score for the sentence.';

-- ---------------------------------------------------------------------------
-- tool_calls: every tool call, refusals included
-- ---------------------------------------------------------------------------
create table if not exists tool_calls (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references users (user_id) on delete cascade,
    tool            text not null,                      -- lookup_lead, search_kb, update_crm, send_tutorial, send_voice_note, send_booking_link
    args            jsonb not null default '{}'::jsonb,
    result          jsonb,
    refused_reason  text,                               -- set when code refused the call (e.g. text_only_mode)
    created_at      timestamptz not null default now()
);
create index if not exists tool_calls_user_created_idx on tool_calls (user_id, created_at);
comment on table tool_calls is 'Tool calls made by the agent, with the reason when code refused one.';
comment on column tool_calls.refused_reason is 'Null when the call ran; otherwise why code refused it.';

-- ---------------------------------------------------------------------------
-- events: funnel milestones
-- ---------------------------------------------------------------------------
create table if not exists events (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid references users (user_id) on delete cascade,   -- null for system events
    type        text not null,                          -- email_sent, token_redeemed, mode_chosen, qualified, booked ...
    payload     jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);
create index if not exists events_type_created_idx on events (type, created_at);
create index if not exists events_user_idx on events (user_id);
comment on table events is 'Funnel milestones. Growth metrics are computed from these rows.';
comment on column events.type is 'Event name, e.g. email_sent, token_redeemed, mode_chosen, qualified, booked.';

-- ---------------------------------------------------------------------------
-- email_drafts: approval queue for replies to incoming email
-- ---------------------------------------------------------------------------
create table if not exists email_drafts (
    id                    uuid primary key default gen_random_uuid(),
    user_id               uuid not null references users (user_id) on delete cascade,
    in_reply_to           uuid references messages (id) on delete set null,
    classification        text not null check (classification in ('interested', 'question', 'not_now', 'unsubscribe')),
    draft_text            text not null,
    final_text            text,                         -- text actually approved; differs from draft_text when edited
    status                text not null default 'pending'
                          check (status in ('pending', 'approved', 'rejected', 'sent')),
    decided_at            timestamptz,
    created_at            timestamptz not null default now()
);
create index if not exists email_drafts_status_idx on email_drafts (status, created_at);
comment on table email_drafts is 'Drafted email replies waiting for human approval. Nothing is sent without approval.';
comment on column email_drafts.classification is 'Reply-sorter label for the incoming email.';
comment on column email_drafts.final_text is 'Approved text. Equal to draft_text means approved unchanged.';

-- ---------------------------------------------------------------------------
-- kb_chunks: knowledge base for retrieval
-- ---------------------------------------------------------------------------
create table if not exists kb_chunks (
    id            uuid primary key default gen_random_uuid(),
    company       text not null,
    source        text not null,                        -- source URL or path
    collected_at  date not null,
    content       text not null,
    embedding     vector(1536),                         -- ADJUST to the dimension of the chosen embedding model
    created_at    timestamptz not null default now()
);
create index if not exists kb_chunks_company_idx on kb_chunks (company);
create index if not exists kb_chunks_embedding_idx on kb_chunks using hnsw (embedding vector_cosine_ops);
comment on table kb_chunks is 'Chunks of public company documents with embeddings, for search_kb.';
comment on column kb_chunks.collected_at is 'Date the source page was collected. Answers must respect it.';
comment on column kb_chunks.embedding is 'Vector size must match EMBED_MODEL.';

-- ---------------------------------------------------------------------------
-- Evals, shaped like Braintrust so runs can be pushed to or compared with it.
--   dataset record -> input, expected, metadata, tags
--   experiment row -> input, output, expected, scores (0..1), metadata, tags, metrics,
--                     span_attributes (span_type, span_name), span_id, root_span_id, span_parents
-- ---------------------------------------------------------------------------
create table if not exists eval_datasets (
    id           uuid primary key default gen_random_uuid(),
    name         text not null unique,
    description  text,
    metadata     jsonb not null default '{}'::jsonb,
    created_at   timestamptz not null default now()
);
comment on table eval_datasets is 'Named sets of eval cases (e.g. labelled injections, benign decoys).';

create table if not exists eval_dataset_records (
    id          uuid primary key default gen_random_uuid(),
    dataset_id  uuid not null references eval_datasets (id) on delete cascade,
    input       jsonb,
    expected    jsonb,
    metadata    jsonb not null default '{}'::jsonb,
    tags        text[] not null default '{}',
    created_at  timestamptz not null default now()
);
create index if not exists eval_dataset_records_dataset_idx on eval_dataset_records (dataset_id);
comment on table eval_dataset_records is 'One eval case. Same fields as a Braintrust dataset record.';
comment on column eval_dataset_records.input is 'The case input. Must not contain experiment-specific state.';
comment on column eval_dataset_records.expected is 'Ground truth. Not compared to output automatically.';

create table if not exists eval_experiments (
    id                       uuid primary key default gen_random_uuid(),
    name                     text not null,
    version                  text,                      -- e.g. v1, v2, before_guards, after_guards
    suite                    text not null check (suite in ('performance', 'security')),
    description              text,
    dataset_id               uuid references eval_datasets (id) on delete set null,
    braintrust_experiment_id text,                      -- set when the run was also sent to Braintrust
    metadata                 jsonb not null default '{}'::jsonb,
    tags                     text[] not null default '{}',
    created_at               timestamptz not null default now()
);
create index if not exists eval_experiments_created_idx on eval_experiments (created_at);
comment on table eval_experiments is 'One eval run of one suite on one version of the system.';
comment on column eval_experiments.version is 'Label used to compare runs (v1 vs v2, before vs after guards).';

-- scores must be an object whose values are numbers between 0 and 1 (or null), as in Braintrust
create or replace function eval_scores_valid(s jsonb) returns boolean
language sql immutable as $$
    select jsonb_typeof(s) = 'object'
       and not exists (
            select 1 from jsonb_each(s) e
            where jsonb_typeof(e.value) not in ('number', 'null')
               or (jsonb_typeof(e.value) = 'number' and (e.value #>> '{}')::numeric not between 0 and 1)
       );
$$;

create table if not exists eval_results (
    id                uuid primary key default gen_random_uuid(),
    experiment_id     uuid not null references eval_experiments (id) on delete cascade,
    dataset_record_id uuid references eval_dataset_records (id) on delete set null,
    span_id           text not null,
    root_span_id      text not null,                    -- identifies the whole trace
    span_parents      text[] not null default '{}',
    span_type         text check (span_type in ('eval', 'task', 'llm', 'function', 'tool', 'score', 'classifier')),
    span_name         text,
    input             jsonb,
    output            jsonb,
    expected          jsonb,
    error             text,
    scores            jsonb not null default '{}'::jsonb check (eval_scores_valid(scores)),
    metadata          jsonb not null default '{}'::jsonb,
    tags              text[] not null default '{}',
    metrics           jsonb not null default '{}'::jsonb,  -- start, end, tokens, prompt_tokens, completion_tokens, cost, latency_ms ...
    created_at        timestamptz not null default now(),
    unique (experiment_id, span_id)
);
create index if not exists eval_results_experiment_idx on eval_results (experiment_id);
create index if not exists eval_results_root_idx on eval_results (root_span_id);
comment on table eval_results is 'One row per span of an eval trace. The root span of a test case has span_type eval.';
comment on column eval_results.scores is 'Scorer name to value between 0 and 1.';
comment on column eval_results.metrics is 'Numbers only: timing, token counts, cost.';
comment on column eval_results.span_parents is 'Span ids of the parents, empty for the root span.';

-- ---------------------------------------------------------------------------
-- Row-level security: on everywhere, no policies. Only the service role can read or write.
-- ---------------------------------------------------------------------------
alter table users                 enable row level security;
alter table crm                   enable row level security;
alter table messages              enable row level security;
alter table masked_messages       enable row level security;
alter table tool_calls            enable row level security;
alter table events                enable row level security;
alter table email_drafts          enable row level security;
alter table kb_chunks             enable row level security;
alter table eval_datasets         enable row level security;
alter table eval_dataset_records  enable row level security;
alter table eval_experiments      enable row level security;
alter table eval_results          enable row level security;

revoke all on table users, crm, messages, masked_messages, tool_calls, events, email_drafts,
    kb_chunks, eval_datasets, eval_dataset_records, eval_experiments, eval_results
    from anon, authenticated;
