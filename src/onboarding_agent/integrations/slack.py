"""Slack notification and Socket Mode adapters."""

from ..models import Employee


class SlackNotifier:
    def __init__(self, bot_token: str) -> None:
        try:
            from slack_sdk.web.async_client import AsyncWebClient
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install integrations with: uv sync --extra integrations") from exc
        self.client = AsyncWebClient(token=bot_token)

    async def notify_employee(self, employee: Employee, text: str) -> None:
        if not employee.slack_user_id:
            raise ValueError("Employee has no verified Slack identity")
        await self.client.chat_postMessage(channel=employee.slack_user_id, text=text)

    async def notify_owner(self, employee: Employee, text: str) -> None:
        lookup = await self.client.users_lookupByEmail(email=employee.onboarding_owner_email)
        owner_id = lookup["user"]["id"]
        await self.client.chat_postMessage(channel=owner_id, text=text)
