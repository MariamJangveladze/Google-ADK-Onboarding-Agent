CREATE TABLE IF NOT EXISTS task_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tasks JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    slack_user_id TEXT UNIQUE,
    timezone TEXT NOT NULL DEFAULT 'Asia/Tbilisi',
    preferred_language TEXT NOT NULL DEFAULT 'ka'
        CHECK (preferred_language IN ('ka', 'en', 'ru')),
    task_template_id TEXT REFERENCES task_templates(id),
    owner_name TEXT NOT NULL DEFAULT 'HR',
    owner_email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS onboarding_sessions (
    employee_id TEXT PRIMARY KEY REFERENCES employees(id) ON DELETE CASCADE,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS onboarding_progress (
    employee_id TEXT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    task_snapshot JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('SENT', 'DONE')),
    sent_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    sla_events JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (employee_id, task_id)
);

CREATE INDEX IF NOT EXISTS onboarding_progress_active_idx
    ON onboarding_progress (status, sent_at)
    WHERE completed_at IS NULL;
