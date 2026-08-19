# Security and privacy baseline

The onboarding domain contains employee identity, progress, sentiment, and conversation data. This
implementation therefore uses the following boundaries:

- Slack identity is bound only through the verified email on the Slack profile.
- The model cannot bind identities, assign tasks, complete tasks, or send escalations.
- Google ADK receives structured context but no database-writing tools.
- Retrieved Drive content is labeled untrusted data to reduce prompt-injection authority.
- Drive access is read-only and should target a dedicated, approved folder.
- Database queries are parameterized and connection credentials come from runtime secrets.
- Raw `.env` and service-account files are excluded from version control.
- Quiet hours apply to both task delivery and SLA notifications.

Before production, add SSO-based authorization, Slack app installation controls, KMS-managed secrets,
PII classification, approved retention and deletion schedules, audit-log export, rate limiting,
dependency scanning, and a documented employee notice for AI-assisted sentiment processing.
