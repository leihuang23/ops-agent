from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.tracing import AgentTraceHandle
from app.models import AgentRun, AgentRunStep

T = TypeVar("T")


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AgentRunRecorder:
    _COMMIT_EVERY = 5

    def __init__(
        self, session: Session, run: AgentRun, trace: AgentTraceHandle | None = None
    ) -> None:
        self.session = session
        self.run = run
        self.trace = trace
        self._next_sequence: int | None = None
        self._steps_since_commit = 0

    def record(
        self,
        *,
        stage: str,
        inputs: object,
        action: Callable[[], T],
        tool_name: str | None = None,
    ) -> T:
        step = self._start_step(stage=stage, tool_name=tool_name, inputs=inputs)
        try:
            # Wrap the action in a SAVEPOINT so that DB changes made by a
            # failing action are rolled back without discarding previously
            # flushed (or committed) steps in the outer transaction. Some
            # action callables (e.g. propose_actions_for_report) call
            # session.commit() internally, which releases the SAVEPOINT; guard
            # with is_active so we don't touch a closed transaction.
            savepoint = self.session.begin_nested()
            try:
                if self.trace is not None:
                    output = self.trace.record_child(
                        name=tool_name or stage,
                        run_type="tool" if tool_name else "chain",
                        inputs=inputs,
                        action=action,
                    )
                else:
                    output = action()
                if savepoint.is_active:
                    savepoint.commit()
            except Exception:
                if savepoint.is_active:
                    savepoint.rollback()
                raise
        except Exception as exc:
            self._fail_step(step.id, exc)
            raise

        self._complete_step(step.id, output)
        return output

    def _touch_run_heartbeat(self) -> None:
        self.run.updated_at = utcnow_naive()

    def _start_step(
        self, *, stage: str, tool_name: str | None, inputs: object
    ) -> AgentRunStep:
        now = utcnow_naive()
        sequence = self._allocate_sequence()
        step = AgentRunStep(
            id=f"step_{uuid4().hex[:16]}",
            run_id=self.run.id,
            sequence=sequence,
            stage=stage,
            tool_name=tool_name,
            status="running",
            inputs=jsonable_encoder(inputs),
            outputs=None,
            error=None,
            started_at=now,
            completed_at=None,
            created_at=now,
        )
        self.session.add(step)
        self._touch_run_heartbeat()
        self.session.flush()
        return step

    def _allocate_sequence(self) -> int:
        if self._next_sequence is None:
            current_max = int(
                self.session.scalar(
                    select(func.coalesce(func.max(AgentRunStep.sequence), 0)).where(
                        AgentRunStep.run_id == self.run.id
                    )
                )
                or 0
            )
            self._next_sequence = current_max + 1

        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def _complete_step(self, step_id: str, output: object) -> None:
        now = utcnow_naive()
        step = self.session.get(AgentRunStep, step_id)
        if step is None:
            raise RuntimeError(f"Agent run step disappeared: {step_id}")
        step.status = "succeeded"
        step.outputs = jsonable_encoder(output)
        step.completed_at = now
        self._touch_run_heartbeat()
        self.session.flush()
        self._maybe_commit()

    def _maybe_commit(self) -> None:
        self._steps_since_commit += 1
        if self._steps_since_commit >= self._COMMIT_EVERY:
            self.session.commit()
            self._steps_since_commit = 0

    def _fail_step(self, step_id: str, exc: Exception) -> None:
        # The SAVEPOINT in record() already rolled back the action's changes.
        # The step row was flushed before the SAVEPOINT, so it survives and
        # we can update it in place. Always commit failures immediately so
        # they are visible in the run history without waiting for a batch.
        now = utcnow_naive()
        step = self.session.get(AgentRunStep, step_id)
        if step is not None:
            step.status = "failed"
            step.error = str(exc)
            step.completed_at = now
            self._touch_run_heartbeat()
            self.session.commit()
            self._steps_since_commit = 0
