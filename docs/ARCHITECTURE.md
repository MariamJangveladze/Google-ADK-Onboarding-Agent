# Architecture decisions

## LLM boundary

Google ADK and Gemini handle multilingual conversation, intent, sentiment, and grounded policy
answers. They do not receive write tools. The workflow service owns identity, task state, quiet
hours, completion, reminders, and HR escalation. This keeps consequential actions testable and
auditable.

## Identity

Live Slack conversations use the email returned by Slack's authenticated profile API. PostgreSQL
binds that Slack user ID only when the email matches an existing employee record and the record is
not already bound to another Slack identity.

## Knowledge retrieval

The prototype embedded every Drive document on every question. The portfolio version refreshes an
in-memory semantic index on a configurable interval, then embeds only each incoming query. For a
larger or multi-instance deployment, move indexing to a background job and store vectors in
pgvector or a managed vector database.

## Persistence

PostgreSQL stores employees, task templates, sessions, task snapshots, completion timestamps, and
deduplicated SLA events. Task snapshots preserve what the employee was actually asked to complete
even if a template changes later.

## Local mode

The default mode uses fixtures and a deterministic clock. It demonstrates the complete workflow,
evaluations, and API without transmitting employee data or requiring paid services.
