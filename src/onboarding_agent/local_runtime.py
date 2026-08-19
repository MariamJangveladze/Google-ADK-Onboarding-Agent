"""Deterministic adapters for demos, tests, and CI."""

from datetime import UTC, datetime

from .models import (
    ActiveTask,
    AgentDecision,
    AgentInput,
    Employee,
    SessionState,
    Task,
)


class InMemoryEmployeeRepository:
    def __init__(self) -> None:
        employee = Employee(
            id="EMP-001",
            full_name="Nino Beridze",
            email="nino@example.com",
            timezone="UTC",
            preferred_language="en",
            onboarding_owner_name="Mariam",
            onboarding_owner_email="mariam.hr@example.com",
        )
        self.employees = {employee.id: employee}
        self.sessions: dict[str, SessionState] = {}
        self.tasks = {
            employee.id: [
                Task(
                    id="TASK-001",
                    title="Review the security handbook",
                    description="Read the security handbook and acknowledge the key controls.",
                    sla_hours=24,
                ),
                Task(
                    id="TASK-002",
                    title="Meet your onboarding buddy",
                    description="Schedule a 30-minute introductory meeting with your buddy.",
                    sla_hours=48,
                ),
            ]
        }
        self.completed: dict[str, set[str]] = {employee.id: set()}
        self.active: dict[tuple[str, str], ActiveTask] = {}

    async def bind_verified_identity(self, slack_user_id: str, email: str) -> Employee | None:
        employee = next((item for item in self.employees.values() if item.email == email), None)
        if not employee:
            return None
        if employee.slack_user_id and employee.slack_user_id != slack_user_id:
            return None
        bound = employee.model_copy(update={"slack_user_id": slack_user_id})
        self.employees[bound.id] = bound
        return bound

    async def get_employee_by_slack(self, slack_user_id: str) -> Employee | None:
        return next(
            (item for item in self.employees.values() if item.slack_user_id == slack_user_id),
            None,
        )

    async def get_session(self, employee_id: str) -> SessionState:
        employee = self.employees[employee_id]
        return self.sessions.get(
            employee_id,
            SessionState(employee_id=employee_id, language=employee.preferred_language),
        ).model_copy(deep=True)

    async def save_session(self, state: SessionState) -> None:
        self.sessions[state.employee_id] = state.model_copy(deep=True)

    async def get_next_task(self, employee_id: str) -> Task | None:
        current = self.sessions.get(employee_id)
        if current and current.current_task:
            return current.current_task
        return next(
            (
                task
                for task in self.tasks.get(employee_id, [])
                if task.id not in self.completed[employee_id]
            ),
            None,
        )

    async def mark_task_sent(self, employee_id: str, task: Task, sent_at: datetime) -> None:
        self.active[(employee_id, task.id)] = ActiveTask(
            employee=self.employees[employee_id], task=task, sent_at=sent_at
        )

    async def complete_task(self, employee_id: str, task_id: str) -> None:
        self.completed[employee_id].add(task_id)
        self.active.pop((employee_id, task_id), None)

    async def list_active_tasks(self) -> list[ActiveTask]:
        return [item.model_copy(deep=True) for item in self.active.values()]

    async def record_sla_event(self, employee_id: str, task_id: str, event: str) -> None:
        active = self.active[(employee_id, task_id)]
        active.emitted_events.add(event)

    def reset(self) -> None:
        for employee_id, employee in list(self.employees.items()):
            self.employees[employee_id] = employee.model_copy(update={"slack_user_id": None})
        self.sessions.clear()
        self.active.clear()
        self.completed = {employee_id: set() for employee_id in self.employees}


class LocalKnowledgeBase:
    async def search(self, query: str) -> tuple[str, list[str]]:
        value = query.casefold()
        if "welcome" in value:
            return (
                "Welcome to Acme Bank. Your first week is designed to help you learn safely, "
                "meet your colleagues, and understand how we serve customers.",
                ["People Handbook / Welcome"],
            )
        return (
            "Employees must protect customer information, use approved systems, and report "
            "suspected security incidents immediately.",
            ["Security Handbook / Information Protection"],
        )


class DeterministicConversationAgent:
    async def respond(self, payload: AgentInput) -> AgentDecision:
        language = payload.language
        if payload.retrieved_context:
            prefixes = {
                "en": "From the company guidance:",
                "ka": "კომპანიის სახელმძღვანელოს მიხედვით:",
                "ru": "Согласно руководству компании:",
            }
            reply = f"{prefixes[language]} {payload.retrieved_context}"
            intent = "POLICY_QUERY"
        else:
            replies = {
                "en": "I am here to help with your onboarding. Ask a question or request help.",
                "ka": "მე დაგეხმარებით ონბორდინგში. დამისვით კითხვა ან მოითხოვეთ დახმარება.",
                "ru": "Я помогу с онбордингом. Задайте вопрос или запросите помощь.",
            }
            reply = replies[language]
            intent = "SMALL_TALK"
        return AgentDecision(
            reply_text=reply,
            detected_sentiment="neutral",
            intent=intent,
        )


class RecordingNotifier:
    def __init__(self) -> None:
        self.employee_messages: list[tuple[str, str]] = []
        self.owner_messages: list[tuple[str, str]] = []

    async def notify_employee(self, employee: Employee, text: str) -> None:
        self.employee_messages.append((employee.id, text))

    async def notify_owner(self, employee: Employee, text: str) -> None:
        self.owner_messages.append((employee.id, text))


def utc_now() -> datetime:
    return datetime.now(UTC)
