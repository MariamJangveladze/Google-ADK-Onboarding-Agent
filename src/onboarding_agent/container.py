"""Application dependency container."""

from dataclasses import dataclass
from datetime import UTC, datetime

from .config import Settings
from .local_runtime import (
    DeterministicConversationAgent,
    InMemoryEmployeeRepository,
    LocalKnowledgeBase,
    RecordingNotifier,
)
from .service import OnboardingService


@dataclass
class ApplicationContainer:
    service: OnboardingService
    repository: object
    notifier: object


def build_container(settings: Settings) -> ApplicationContainer:
    if settings.runtime_mode == "local":
        repository = InMemoryEmployeeRepository()
        notifier = RecordingNotifier()
        service = OnboardingService(
            repository=repository,
            knowledge=LocalKnowledgeBase(),
            agent=DeterministicConversationAgent(),
            notifier=notifier,
            settings=settings,
            clock=lambda: datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        )
        return ApplicationContainer(service=service, repository=repository, notifier=notifier)

    settings.validate_live()
    from .integrations.google_adk import GoogleAdkConversationAgent
    from .integrations.google_drive import GoogleDriveKnowledgeBase
    from .integrations.postgres import PostgresEmployeeRepository
    from .integrations.slack import SlackNotifier

    repository = PostgresEmployeeRepository(settings.database_url)
    notifier = SlackNotifier(settings.slack_bot_token)
    service = OnboardingService(
        repository=repository,
        knowledge=GoogleDriveKnowledgeBase(settings),
        agent=GoogleAdkConversationAgent(settings),
        notifier=notifier,
        settings=settings,
    )
    return ApplicationContainer(service=service, repository=repository, notifier=notifier)
