"""Slack Socket Mode entry point for live deployments."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from .config import get_settings
from .container import build_container

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    settings.validate_live()
    container = build_container(settings)
    slack = AsyncApp(token=settings.slack_bot_token)
    user_locks: dict[str, asyncio.Lock] = {}

    def lock_for(user_id: str) -> asyncio.Lock:
        return user_locks.setdefault(user_id, asyncio.Lock())

    @slack.event("message")
    async def handle_message(event, say):
        if event.get("bot_id") or not event.get("text"):
            return
        if event.get("channel_type") != "im":
            return
        user_id = event["user"]
        async with lock_for(user_id):
            employee = await container.service.repository.get_employee_by_slack(user_id)
            if not employee:
                profile = await slack.client.users_info(user=user_id)
                email = profile["user"]["profile"].get("email")
                if not email:
                    await say("Your verified Slack profile has no company email address.")
                    return
                response = await container.service.start_employee(user_id, email)
            else:
                response = await container.service.handle_message(user_id, event["text"])
            await say(response.text)

    @slack.action("task_done_click")
    async def done(ack, body):
        await ack()
        user_id = body["user"]["id"]
        async with lock_for(user_id):
            response = await container.service.handle_message(user_id, "done")
            await slack.client.chat_postMessage(channel=body["channel"]["id"], text=response.text)

    @slack.action("task_help_click")
    async def help_request(ack, body):
        await ack()
        user_id = body["user"]["id"]
        async with lock_for(user_id):
            response = await container.service.handle_message(user_id, "help")
            await slack.client.chat_postMessage(channel=body["channel"]["id"], text=response.text)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(container.service.run_sla_sweep, "interval", minutes=5)
    scheduler.start()
    await AsyncSocketModeHandler(slack, settings.slack_app_token).start_async()


if __name__ == "__main__":
    asyncio.run(run())
