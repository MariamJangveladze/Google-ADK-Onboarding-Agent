# Portfolio case study

## Problem

Employee onboarding often spans static documents, HR spreadsheets, chat messages, task templates,
and manual follow-ups. New hires struggle to find authoritative answers while HR repeatedly checks
progress and chases overdue tasks.

## Solution

This agent proactively welcomes verified employees in Slack, retrieves approved guidance from
Google Drive, delivers role-specific tasks, respects local quiet hours, records progress, detects
blockers, and escalates help or overdue work to the human onboarding owner.

## AI and automation split

Gemini through Google ADK handles language, sentiment, intent, and grounded conversation. Normal
application code owns workflow state and side effects. This demonstrates a practical enterprise
agent pattern rather than delegating the entire process to an unconstrained model.

## Adoption outcomes to measure

- Time from hire creation to first successful contact
- Task completion lead time and SLA breach rate
- Percentage of policy questions resolved with approved citations
- Human escalation rate and escalation response time
- HR coordination minutes saved per new hire
- Employee satisfaction and failed-answer rate
