"""Domain and API models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["ka", "en", "ru"]


class Task(BaseModel):
    id: str
    title: str
    description: str
    sla_hours: int = Field(default=24, ge=1, le=720)


class Employee(BaseModel):
    id: str
    full_name: str
    email: str
    slack_user_id: str | None = None
    timezone: str = "Asia/Tbilisi"
    preferred_language: Language = "ka"
    onboarding_owner_name: str = "HR"
    onboarding_owner_email: str = "hr@example.com"


class SessionState(BaseModel):
    employee_id: str
    history: list[dict[str, str]] = Field(default_factory=list)
    current_task: Task | None = None
    current_task_sent_at: datetime | None = None
    welcome_sent: bool = False
    language: Language = "ka"


class AgentInput(BaseModel):
    message: str
    employee_first_name: str
    language: Language
    current_task: Task | None = None
    retrieved_context: str = ""


class AgentDecision(BaseModel):
    reply_text: str
    detected_sentiment: Literal["positive", "neutral", "frustrated", "confused"]
    intent: Literal["GREETING", "TASK_HELP", "POLICY_QUERY", "SMALL_TALK"]
    needs_hr_intervention: bool = False
    is_sla_warning: bool = False


class BotResponse(BaseModel):
    text: str
    language: Language
    action: Literal[
        "WELCOME",
        "TASK_ASSIGNED",
        "TASK_COMPLETED",
        "HELP_ESCALATED",
        "QUIET_HOURS",
        "ANSWER",
        "ALL_TASKS_COMPLETE",
        "IDENTITY_REQUIRED",
    ]
    task: Task | None = None
    citations: list[str] = Field(default_factory=list)
    needs_hr_intervention: bool = False


class ActiveTask(BaseModel):
    employee: Employee
    task: Task
    sent_at: datetime
    emitted_events: set[str] = Field(default_factory=set)


class DemoStartRequest(BaseModel):
    slack_user_id: str = "U_DEMO"
    verified_email: str = "nino@example.com"


class ChatRequest(BaseModel):
    slack_user_id: str = "U_DEMO"
    message: str = Field(min_length=1, max_length=2000)


class ActionRequest(BaseModel):
    slack_user_id: str = "U_DEMO"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    runtime_mode: Literal["local", "live"]
    service: str = "google-adk-onboarding-agent"
