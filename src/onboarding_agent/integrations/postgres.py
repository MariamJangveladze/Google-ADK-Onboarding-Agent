"""PostgreSQL persistence adapter for live onboarding state."""

import asyncio
import json
from datetime import datetime

from ..models import ActiveTask, Employee, SessionState, Task


class PostgresEmployeeRepository:
    def __init__(self, database_url: str) -> None:
        try:
            from psycopg_pool import AsyncConnectionPool
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install integrations with: uv sync --extra integrations") from exc
        self.pool = AsyncConnectionPool(database_url, min_size=1, max_size=10, open=False)
        self._opened = False
        self._open_lock = asyncio.Lock()

    async def _ensure_open(self) -> None:
        if self._opened:
            return
        async with self._open_lock:
            if not self._opened:
                await self.pool.open()
                self._opened = True

    @staticmethod
    def _employee(row: dict) -> Employee:
        return Employee(
            id=str(row["id"]),
            full_name=row["full_name"],
            email=row["email"],
            slack_user_id=row.get("slack_user_id"),
            timezone=row.get("timezone") or "Asia/Tbilisi",
            preferred_language=row.get("preferred_language") or "ka",
            onboarding_owner_name=row.get("owner_name") or "HR",
            onboarding_owner_email=row.get("owner_email") or "hr@example.com",
        )

    async def bind_verified_identity(self, slack_user_id: str, email: str) -> Employee | None:
        await self._ensure_open()
        from psycopg.rows import dict_row

        async with (
            self.pool.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                """
                UPDATE employees
                SET slack_user_id = %s, updated_at = NOW()
                WHERE lower(email) = lower(%s)
                  AND (slack_user_id IS NULL OR slack_user_id = %s)
                RETURNING *
                """,
                (slack_user_id, email, slack_user_id),
            )
            row = await cursor.fetchone()
            return self._employee(row) if row else None

    async def get_employee_by_slack(self, slack_user_id: str) -> Employee | None:
        await self._ensure_open()
        from psycopg.rows import dict_row

        async with (
            self.pool.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                "SELECT * FROM employees WHERE slack_user_id = %s",
                (slack_user_id,),
            )
            row = await cursor.fetchone()
            return self._employee(row) if row else None

    async def get_session(self, employee_id: str) -> SessionState:
        await self._ensure_open()
        async with self.pool.connection() as connection, connection.cursor() as cursor:
            await cursor.execute(
                "SELECT state FROM onboarding_sessions WHERE employee_id = %s",
                (employee_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return SessionState(employee_id=employee_id)
            state = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            return SessionState.model_validate(state)

    async def save_session(self, state: SessionState) -> None:
        await self._ensure_open()
        async with self.pool.connection() as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                    INSERT INTO onboarding_sessions (employee_id, state, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (employee_id) DO UPDATE
                    SET state = EXCLUDED.state, updated_at = NOW()
                    """,
                (state.employee_id, state.model_dump_json()),
            )

    async def get_next_task(self, employee_id: str) -> Task | None:
        await self._ensure_open()
        async with self.pool.connection() as connection, connection.cursor() as cursor:
            await cursor.execute(
                "SELECT tasks FROM task_templates WHERE id = "
                "(SELECT task_template_id FROM employees WHERE id = %s)",
                (employee_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            raw_tasks = row[0] if isinstance(row[0], list) else json.loads(row[0])
            await cursor.execute(
                "SELECT task_id FROM onboarding_progress "
                "WHERE employee_id = %s AND status = 'DONE'",
                (employee_id,),
            )
            completed = {item[0] for item in await cursor.fetchall()}
            return next(
                (Task.model_validate(task) for task in raw_tasks if task["id"] not in completed),
                None,
            )

    async def mark_task_sent(self, employee_id: str, task: Task, sent_at: datetime) -> None:
        await self._ensure_open()
        async with self.pool.connection() as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                    INSERT INTO onboarding_progress
                        (employee_id, task_id, task_snapshot, status, sent_at, sla_events)
                    VALUES (%s, %s, %s::jsonb, 'SENT', %s, '[]'::jsonb)
                    ON CONFLICT (employee_id, task_id) DO UPDATE
                    SET task_snapshot = EXCLUDED.task_snapshot,
                        status = 'SENT', sent_at = EXCLUDED.sent_at, updated_at = NOW()
                    """,
                (employee_id, task.id, task.model_dump_json(), sent_at),
            )

    async def complete_task(self, employee_id: str, task_id: str) -> None:
        await self._ensure_open()
        async with self.pool.connection() as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                    UPDATE onboarding_progress
                    SET status = 'DONE', completed_at = NOW(), updated_at = NOW()
                    WHERE employee_id = %s AND task_id = %s
                    """,
                (employee_id, task_id),
            )

    async def list_active_tasks(self) -> list[ActiveTask]:
        await self._ensure_open()
        from psycopg.rows import dict_row

        async with (
            self.pool.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(
                """
                SELECT p.employee_id, p.task_snapshot, p.sent_at, p.sla_events, e.*
                FROM onboarding_progress p
                JOIN employees e ON e.id = p.employee_id
                WHERE p.status = 'SENT' AND p.completed_at IS NULL
                """
            )
            rows = await cursor.fetchall()
        results = []
        for row in rows:
            raw_task = row["task_snapshot"]
            raw_events = row["sla_events"] or []
            results.append(
                ActiveTask(
                    employee=self._employee(row),
                    task=Task.model_validate(raw_task),
                    sent_at=row["sent_at"],
                    emitted_events=set(raw_events),
                )
            )
        return results

    async def record_sla_event(self, employee_id: str, task_id: str, event: str) -> None:
        await self._ensure_open()
        async with self.pool.connection() as connection, connection.cursor() as cursor:
            await cursor.execute(
                """
                    UPDATE onboarding_progress
                    SET sla_events = COALESCE(sla_events, '[]'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE employee_id = %s AND task_id = %s
                    """,
                (json.dumps([event]), employee_id, task_id),
            )
