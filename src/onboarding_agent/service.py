"""Deterministic onboarding workflow with AI at bounded interpretation points."""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .language import detect_language, is_done, is_help, is_policy_query, is_ready
from .models import AgentInput, BotResponse, Employee, Language, SessionState
from .ports import ConversationAgent, EmployeeRepository, KnowledgeBase, Notifier

logger = logging.getLogger("onboarding_agent")


class OnboardingService:
    def __init__(
        self,
        repository: EmployeeRepository,
        knowledge: KnowledgeBase,
        agent: ConversationAgent,
        notifier: Notifier,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.knowledge = knowledge
        self.agent = agent
        self.notifier = notifier
        self.settings = settings
        self.clock = clock or (lambda: datetime.now(UTC))

    def _is_quiet_hours(self, timezone_name: str, now: datetime | None = None) -> bool:
        try:
            timezone_value = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            timezone_value = UTC
        current = (now or self.clock()).astimezone(timezone_value)
        start = self.settings.quiet_hours_start
        end = self.settings.quiet_hours_end
        if start < end:
            return start <= current.hour < end
        return current.hour >= start or current.hour < end

    @staticmethod
    def _first_name(employee: Employee) -> str:
        return employee.full_name.split()[0]

    @staticmethod
    def _copy(language: Language, key: str, **values: str) -> str:
        messages = {
            "identity": {
                "en": "I could not verify your Slack identity against an onboarding record.",
                "ka": "თქვენი Slack იდენტობა ონბორდინგის ჩანაწერთან ვერ დადასტურდა.",
                "ru": "Не удалось подтвердить вашу личность Slack по записи онбординга.",
            },
            "ready": {
                "en": "Are you ready to begin your onboarding tasks?",
                "ka": "მზად ხართ ონბორდინგის დავალებების დასაწყებად?",
                "ru": "Вы готовы начать задания по онбордингу?",
            },
            "quiet": {
                "en": "It is currently quiet hours for you. Please rest and continue tomorrow.",
                "ka": "ახლა თქვენთვის წყნარი საათებია. დაისვენეთ და გავაგრძელოთ ხვალ.",
                "ru": "Сейчас у вас тихие часы. Отдохните и продолжим завтра.",
            },
            "task": {
                "en": "Your next task is {title}: {description}",
                "ka": "თქვენი შემდეგი დავალებაა {title}: {description}",
                "ru": "Ваше следующее задание — {title}: {description}",
            },
            "complete": {
                "en": "Task completed. Great work.",
                "ka": "დავალება დასრულებულია. შესანიშნავია.",
                "ru": "Задание выполнено. Отличная работа.",
            },
            "all_done": {
                "en": "Congratulations, you have completed all onboarding tasks!",
                "ka": "გილოცავთ, ონბორდინგის ყველა დავალება დასრულებულია!",
                "ru": "Поздравляем, вы выполнили все задания по онбордингу!",
            },
            "help": {
                "en": "I notified {owner}. They will reach out to help you.",
                "ka": "დახმარების მოთხოვნა გავუგზავნე {owner}-ს. ისინი დაგიკავშირდებიან.",
                "ru": "Я уведомил {owner}. С вами свяжутся и помогут.",
            },
        }
        return messages[key][language].format(**values)

    async def start_employee(self, slack_user_id: str, verified_email: str) -> BotResponse:
        employee = await self.repository.bind_verified_identity(slack_user_id, verified_email)
        if not employee:
            return BotResponse(
                text=self._copy("en", "identity"),
                language="en",
                action="IDENTITY_REQUIRED",
            )
        state = await self.repository.get_session(employee.id)
        language = employee.preferred_language
        context, citations = await self.knowledge.search("official onboarding welcome")
        text = f"Hi {self._first_name(employee)},\n\n{context}\n\n{self._copy(language, 'ready')}"
        state.welcome_sent = True
        state.language = language
        state.history.extend([{"role": "assistant", "content": text}])
        await self.repository.save_session(state)
        self._log("welcome_sent", employee.id, action="WELCOME")
        return BotResponse(
            text=text,
            language=language,
            action="WELCOME",
            citations=citations,
        )

    async def handle_message(self, slack_user_id: str, message: str) -> BotResponse:
        employee = await self.repository.get_employee_by_slack(slack_user_id)
        if not employee:
            return BotResponse(
                text=self._copy("en", "identity"),
                language="en",
                action="IDENTITY_REQUIRED",
            )
        state = await self.repository.get_session(employee.id)
        language = detect_language(message, state.language)
        state.language = language
        if is_done(message):
            return await self.complete_current_task(employee, state)
        if is_help(message):
            return await self.request_help(employee, state)
        if is_ready(message) and not state.current_task:
            return await self.assign_next_task(employee, state)

        context = ""
        citations: list[str] = []
        if is_policy_query(message):
            context, citations = await self.knowledge.search(message)
        decision = await self.agent.respond(
            AgentInput(
                message=message,
                employee_id=employee.id,
                employee_first_name=self._first_name(employee),
                language=language,
                current_task=state.current_task,
                retrieved_context=context,
            )
        )
        state.history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": decision.reply_text},
            ]
        )
        state.history = state.history[-20:]
        await self.repository.save_session(state)
        if decision.needs_hr_intervention:
            await self.notifier.notify_owner(
                employee,
                f"{employee.full_name} needs human onboarding support.",
            )
        self._log("message_processed", employee.id, intent=decision.intent)
        return BotResponse(
            text=decision.reply_text,
            language=language,
            action="ANSWER",
            citations=citations,
            needs_hr_intervention=decision.needs_hr_intervention,
        )

    async def assign_next_task(
        self, employee: Employee, state: SessionState, now: datetime | None = None
    ) -> BotResponse:
        if self._is_quiet_hours(employee.timezone, now):
            return BotResponse(
                text=self._copy(state.language, "quiet"),
                language=state.language,
                action="QUIET_HOURS",
            )
        task = await self.repository.get_next_task(employee.id)
        if not task:
            return BotResponse(
                text=self._copy(state.language, "all_done"),
                language=state.language,
                action="ALL_TASKS_COMPLETE",
            )
        sent_at = now or self.clock()
        await self.repository.mark_task_sent(employee.id, task, sent_at)
        state.current_task = task
        state.current_task_sent_at = sent_at
        text = self._copy(
            state.language,
            "task",
            title=task.title,
            description=task.description,
        )
        state.history.append({"role": "assistant", "content": text})
        await self.repository.save_session(state)
        self._log("task_assigned", employee.id, task_id=task.id)
        return BotResponse(
            text=text,
            language=state.language,
            action="TASK_ASSIGNED",
            task=task,
        )

    async def complete_current_task(self, employee: Employee, state: SessionState) -> BotResponse:
        if not state.current_task:
            return BotResponse(
                text="There is no active task to complete.",
                language=state.language,
                action="ANSWER",
            )
        task_id = state.current_task.id
        await self.repository.complete_task(employee.id, task_id)
        state.current_task = None
        state.current_task_sent_at = None
        await self.repository.save_session(state)
        next_response = await self.assign_next_task(employee, state)
        if next_response.action == "TASK_ASSIGNED":
            next_response.text = f"{self._copy(state.language, 'complete')}\n\n{next_response.text}"
            next_response.action = "TASK_COMPLETED"
        self._log("task_completed", employee.id, task_id=task_id)
        return next_response

    async def request_help(self, employee: Employee, state: SessionState) -> BotResponse:
        task_name = state.current_task.title if state.current_task else "onboarding"
        await self.notifier.notify_owner(
            employee,
            f"{employee.full_name} requested help with {task_name}.",
        )
        self._log("help_escalated", employee.id, task=task_name)
        return BotResponse(
            text=self._copy(state.language, "help", owner=employee.onboarding_owner_name),
            language=state.language,
            action="HELP_ESCALATED",
            needs_hr_intervention=True,
        )

    async def run_sla_sweep(self, now: datetime | None = None) -> dict[str, int]:
        current = now or self.clock()
        counts = {"reminders": 0, "escalations": 0, "quiet_hours_skips": 0}
        for active in await self.repository.list_active_tasks():
            if self._is_quiet_hours(active.employee.timezone, current):
                counts["quiet_hours_skips"] += 1
                continue
            due_at = active.sent_at + timedelta(hours=active.task.sla_hours)
            seconds_left = (due_at - current).total_seconds()
            if seconds_left <= 0 and "OVERDUE" not in active.emitted_events:
                await self.notifier.notify_owner(
                    active.employee,
                    f"{active.employee.full_name} has an overdue task: {active.task.title}.",
                )
                await self.repository.record_sla_event(
                    active.employee.id, active.task.id, "OVERDUE"
                )
                counts["escalations"] += 1
            elif seconds_left <= 3600 and "ONE_HOUR" not in active.emitted_events:
                await self.notifier.notify_employee(
                    active.employee,
                    f"Your task '{active.task.title}' is due within one hour.",
                )
                await self.repository.record_sla_event(
                    active.employee.id, active.task.id, "ONE_HOUR"
                )
                counts["reminders"] += 1
        self._log("sla_sweep_completed", "system", **counts)
        return counts

    @staticmethod
    def _log(event: str, employee_id: str, **details: object) -> None:
        logger.info(json.dumps({"event": event, "employee_id": employee_id, **details}))
