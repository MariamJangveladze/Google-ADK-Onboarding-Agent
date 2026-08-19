from datetime import UTC, datetime, timedelta

import pytest

from onboarding_agent.config import Settings
from onboarding_agent.container import build_container


@pytest.mark.asyncio
async def test_help_request_notifies_human_owner():
    container = build_container(Settings(runtime_mode="local"))
    await container.service.start_employee("U_DEMO", "nino@example.com")
    await container.service.handle_message("U_DEMO", "ready")

    response = await container.service.handle_message("U_DEMO", "I am stuck and need help")

    assert response.action == "HELP_ESCALATED"
    assert response.needs_hr_intervention is True
    assert len(container.notifier.owner_messages) == 1


@pytest.mark.asyncio
async def test_sla_sweep_reminds_then_escalates_once():
    container = build_container(Settings(runtime_mode="local"))
    employee = await container.repository.bind_verified_identity("U_DEMO", "nino@example.com")
    state = await container.repository.get_session(employee.id)
    task = await container.repository.get_next_task(employee.id)
    sent_at = datetime(2026, 1, 14, 12, 0, tzinfo=UTC)
    await container.repository.mark_task_sent(employee.id, task, sent_at)
    state.current_task = task
    state.current_task_sent_at = sent_at
    await container.repository.save_session(state)

    reminder = await container.service.run_sla_sweep(sent_at + timedelta(hours=23, minutes=30))
    overdue = await container.service.run_sla_sweep(sent_at + timedelta(hours=25))
    duplicate = await container.service.run_sla_sweep(sent_at + timedelta(hours=26))

    assert reminder["reminders"] == 1
    assert overdue["escalations"] == 1
    assert duplicate["escalations"] == 0


@pytest.mark.asyncio
async def test_quiet_hours_prevent_task_assignment():
    container = build_container(Settings(runtime_mode="local"))
    employee = await container.repository.bind_verified_identity("U_DEMO", "nino@example.com")
    state = await container.repository.get_session(employee.id)
    nighttime = datetime(2026, 1, 15, 22, 0, tzinfo=UTC)

    response = await container.service.assign_next_task(employee, state, nighttime)

    assert response.action == "QUIET_HOURS"
    assert not container.repository.active
