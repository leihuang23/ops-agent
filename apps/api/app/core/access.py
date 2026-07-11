from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

DEMO_DATA_ENVIRONMENTS = {"local", "test", "development", "demo"}


def require_demo_data_access() -> None:
    settings = get_settings()
    if settings.app_env not in DEMO_DATA_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Demo data endpoints are only available in local, test, "
                "development, or demo environments."
            ),
        )


def require_demo_operator_access(
    demo_operator_token: str | None = Header(default=None, alias="X-Demo-Operator-Token"),
) -> None:
    require_demo_data_access()
    settings = get_settings()
    if settings.demo_operator_token is None:
        if settings.app_env == "demo":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Demo mutation API is disabled. Set DEMO_OPERATOR_TOKEN "
                    "and pass X-Demo-Operator-Token for public demo writes."
                ),
            )
        return

    if demo_operator_token is None or not secrets.compare_digest(
        demo_operator_token, settings.demo_operator_token
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid demo operator token.",
        )


def require_operator_or_eval_run_access(
    demo_operator_token: str | None = Header(default=None, alias="X-Demo-Operator-Token"),
    eval_run_token: str | None = Header(default=None, alias="X-Eval-Run-Token"),
) -> None:
    """Accept EITHER ``DEMO_OPERATOR_TOKEN`` OR ``EVAL_RUN_TOKEN`` (PRD FR-21).

    Used by ``POST /eval-datasets/{id}/run``, which "also accepts
    ``EVAL_RUN_TOKEN``" — i.e. either credential authorizes the call, so a QA
    evaluator with only an eval-run token can trigger a dataset run without the
    operator token. In ``demo`` the gate fails closed when neither token is
    configured; in non-demo envs it is ungated when neither token is configured
    (consistent with ``require_demo_operator_access`` and FR-21's
    "Local/test/development may run ungated"). Each comparison uses
    ``secrets.compare_digest``.
    """
    require_demo_data_access()
    settings = get_settings()
    op_configured = settings.demo_operator_token
    eval_configured = settings.eval_run_token

    # Non-demo envs run ungated when neither token is configured (FR-21).
    if settings.app_env != "demo" and op_configured is None and eval_configured is None:
        return

    if (
        op_configured is not None
        and demo_operator_token is not None
        and secrets.compare_digest(demo_operator_token, op_configured)
    ):
        return
    if (
        eval_configured is not None
        and eval_run_token is not None
        and secrets.compare_digest(eval_run_token, eval_configured)
    ):
        return

    if settings.app_env == "demo" and op_configured is None and eval_configured is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Eval dataset run API is disabled. Set DEMO_OPERATOR_TOKEN or "
                "EVAL_RUN_TOKEN and pass the corresponding header for public "
                "demo eval runs."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid operator or eval run token.",
    )
