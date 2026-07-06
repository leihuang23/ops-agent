# PRD Completion Plan

> **Status: implemented.** This plan was used to guide the first MVP pass. The
> acceptance criteria below are now satisfied by the current codebase; the
> latest verification numbers and inspection steps are in
> `docs/project-1-run-and-test-runbook.md`.

## Goal

Complete the local MVP contract in `prd.md` for the SaaS Revenue and Support Ops Agent, with evidence that the implemented app satisfies the PRD success criteria and exposes the listed API surface.

## Acceptance Criteria

All criteria are satisfied by the current implementation:

1. ✅ The core API routes listed in `prd.md` are present in the FastAPI OpenAPI schema, plus additional operational routes such as `GET /ready`, `GET /accounts`, `GET /agent/runs`, `GET /support/tickets/{ticket_id}`, `GET /evals/results`, and `GET /evals/runs/{eval_run_id}`.
2. ✅ `GET /metrics/revenue` returns the same revenue metric contract as `/metrics/mrr`.
3. ✅ `GET /accounts/{account_id}` returns account, subscription, invoice, support ticket, and product-event context for seeded accounts.
4. ✅ `GET /support/tickets` lists support tickets with deterministic ordering and filters for account, status, category, and source scenario.
5. ✅ The reviewer UI has smoke coverage for the dashboard, incident detail, agent run detail, approvals queue, accounts list/detail, support tickets, knowledge search, and eval report.
6. ✅ The full backend test suite, frontend tests, frontend typecheck, and frontend production build pass.

## Implementation Steps

The steps below were completed during the MVP pass:

1. ✅ Added failing backend contract tests for the PRD routes in `apps/api/tests/test_prd_api_contract.py`.
2. ✅ Implemented `accounts` and `support` routers and schemas.
3. ✅ Added `/metrics/revenue` as an alias to `/metrics/mrr`.
4. ✅ Added frontend smoke tests in `apps/web/app/reviewerFlowSmoke.test.ts`.
5. ✅ Documented human-assisted follow-ups in `docs/human-assistance.md`.
6. ✅ Verification passes:
   - `cd apps/api && .venv/bin/python -m pytest` — ~163 tests pass.
   - `cd apps/web && npm test` — 8 tests pass.
   - `cd apps/web && npm run lint` — passes.
   - `cd apps/web && npm run build` — passes.

## Human-Assisted Items

Hosted Langfuse/LangSmith verification, Vercel/backend deployment, and real browser inspection of a deployed stack require credentials or external services. They are tracked separately in `docs/human-assistance.md`.
