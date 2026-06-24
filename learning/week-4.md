# Week 4 Learning Guide: Investigation Agent V1

This guide is for reviewing PR #12 as a JavaScript full-stack developer who
wants to understand how the Python/FastAPI/LangGraph parts produce the first
auditable agent investigation report.

The goal is not to build a fully autonomous ops agent yet. The goal is to prove
the important loop: start from an incident, gather evidence through typed tools,
persist every step, validate a structured report, and show the result in a UI a
reviewer can audit.

## What This Slice Proves

This slice turns the seeded MRR-drop incident into the first useful
agent-generated investigation:

- A user can launch an investigation from the incident page.
- The backend creates a persisted agent run and persisted run steps.
- A LangGraph workflow runs intake, planning, metric queries, doc search,
  support-ticket fetch, and report synthesis.
- Typed tools return SQL-style metric evidence, account details, document
  citations, and support tickets.
- The final report is validated against a structured Pydantic schema.
- Failed tool calls are stored and surfaced in the run history.
- The report page shows root cause, affected accounts, cited evidence,
  confidence, next actions, and tool-step history.

You should be able to explain:

- Why the agent report is only credible if it cites retrieved evidence.
- How persisted run steps make the workflow auditable after the request ends.
- Why typed tool inputs and outputs matter more than fluent report prose.
- How the frontend renders both success and failure states.
- Which tests protect against fake intelligence and hidden tool failures.

## 1. Agent Run Models And Migration

Start with:

- `apps/api/app/models.py`
- `apps/api/alembic/versions/20260613_0004_add_agent_runs.py`

Key ideas:

- `AgentRun` is the durable investigation-level record.
- `AgentRunStep` is the audit trail for each workflow node or tool call.
- Runs store status, trace ID, input payload, final report, token estimate,
  cost estimate, errors, and timestamps.
- Steps store sequence, stage, tool name, inputs, outputs, status, errors, and
  timestamps.
- The `(run_id, sequence)` uniqueness constraint makes the timeline stable.
- `Incident.agent_runs` links investigations back to the incident they explain.

Review questions:

- Can a reviewer understand what happened without reading server logs?
- Does every failed tool call have an error and enough input context?
- Are timestamps present for both run-level and step-level auditability?
- Does the migration match the ORM model fields and indexes?

## 2. Typed Agent Tools

Read:

- `apps/api/app/agent/tools.py`
- `apps/api/app/agent/schemas.py`

The tools are intentionally deterministic. The agent synthesizes from evidence;
it does not invent evidence.

Tools added:

- `query_revenue_metrics`
- `fetch_account_details`
- `search_docs`
- `fetch_support_tickets`

Key ideas:

- Pydantic input and output models define the contract for every tool.
- `query_revenue_metrics` returns metric snapshots plus SQL-style evidence.
- SQL evidence includes query text, bound parameters, result rows, and incident
  snapshot values.
- `fetch_account_details` connects accounts, subscriptions, and failed
  invoices.
- `search_docs` returns knowledge chunks with citation metadata from Week 3.
- `fetch_support_tickets` returns ticket evidence ordered by business priority
  before recency.
- Empty account lists are handled gracefully so ambiguous incidents can produce
  low-confidence reports instead of crashing.

Review questions:

- Which tool is responsible for SQL evidence?
- Which fields make SQL evidence replayable or at least inspectable?
- Does the report cite documents that were actually retrieved?
- What happens when there are no affected accounts?
- Are tool outputs shaped for auditability or only for convenience?

## 3. LangGraph Workflow

Read:

- `apps/api/app/agent/workflow.py`
- `apps/api/app/agent/persistence.py`

Workflow stages:

1. `intake`
2. `plan`
3. `query_metrics`
4. `search_docs`
5. `fetch_tickets`
6. `synthesize_report`

Key ideas:

- The graph is explicit and sequential for V1.
- `AgentRunRecorder.record(...)` wraps every node/tool call.
- Each step is committed as `running`, then updated to `succeeded` or `failed`.
- If a tool raises, the failed step is persisted before the exception bubbles.
- Report synthesis validates the raw report with `InvestigationReport`.
- The diagnosis is derived from retrieved invoice reasons, document snippets,
  and ticket text rather than reading seeded scenario metadata.

Review questions:

- Which stage would fail if document search broke?
- Can the run history show the exact tool that failed?
- Does synthesis depend on retrieved tool outputs or hidden seed labels?
- Where would you add another tool without hiding it from the timeline?
- Why is a sequential V1 acceptable for this slice, and when would it need a
  background worker?

## 4. Evidence-Backed Report Validation

Read:

- `apps/api/app/agent/schemas.py`
- `apps/api/app/agent/workflow.py`
- `apps/api/tests/test_agent_investigations.py`

The final report is not just Markdown. It is structured data:

- `root_cause`
- `summary`
- `affected_accounts`
- `cited_evidence`
- `confidence`
- `next_actions`
- `generated_at`

Key ideas:

- `InvestigationReport.model_validate(...)` rejects malformed report output.
- `ReportEvidence.kind` is constrained to `sql`, `document`, or `ticket`.
- SQL citations include parameters and result rows.
- Document citations include stable source and chunk IDs.
- Ticket citations include ticket ID, account context, category, priority, and
  status.
- Confidence is lower when evidence is missing or the diagnosis is not specific.

Review questions:

- Does each major claim have a corresponding citation?
- Are SQL citations empty, or do they include parameters and rows?
- Could the report still say "unknown" when evidence is incomplete?
- Would a UI reviewer know why confidence is high or low?

## 5. Run Service And API Routes

Read:

- `apps/api/app/agent/service.py`
- `apps/api/app/agent/router.py`
- `apps/api/app/main.py`

Endpoints added:

- `POST /agent/investigations`
- `GET /agent/runs/{run_id}`

Key ideas:

- Starting a run first verifies the incident exists.
- By default, starting an investigation reuses an existing `running` or
  `succeeded` run for that incident.
- `force: true` is available for future explicit rerun behavior.
- Failed workflow execution returns a persisted failed run instead of hiding the
  error.
- `GET /agent/runs/{run_id}` returns the report plus ordered step history.
- The router keeps the same demo-data access guard used by other demo surfaces.

Review questions:

- Why should duplicate clicks not create competing successful runs?
- Should a failed run be reusable, or should a retry create a new run?
- Does the API expose failed tool steps clearly enough?
- What changes when this becomes asynchronous later?

## 6. Frontend Launch Flow

Read:

- `apps/web/app/incidents/[incidentId]/page.tsx`
- `apps/web/app/actions.ts`
- `apps/web/lib/api.ts`

Key ideas:

- The incident page now includes a `Run investigation` action.
- The server action calls `startInvestigation(...)` and redirects to the run
  report page.
- Redirect path parts are URL-encoded.
- API client types mirror the backend run, step, report, evidence, and affected
  account schemas.
- Investigation errors redirect back to the incident page with an error message.

Review questions:

- Is the launch action visible from the incident page without adding a new
  dashboard detour?
- Do TypeScript types match the Pydantic response fields?
- What does the user see when investigation start fails?
- Does repeated submission reuse the existing run from the user's perspective?

## 7. Report Page UI

Read:

- `apps/web/app/agent/runs/[runId]/page.tsx`
- `apps/web/app/globals.css`

Key ideas:

- The report page is an operational review surface, not a marketing page.
- The header shows run status and links back to the incident.
- The snapshot bar shows started time, completed time, trace ID, and estimated
  tokens.
- The report grid shows root cause, confidence, next actions, affected
  accounts, and cited evidence.
- SQL evidence renders the query string.
- Document and ticket evidence render stable citation labels.
- Tool-step history shows every step with status, inputs, outputs, and errors.
- Failed runs can still be inspected even when no final report exists.

Review questions:

- Can a reviewer find the SQL query behind the MRR claim?
- Can a reviewer find the knowledge document source ID and chunk ID?
- Are failed tool calls visually obvious?
- Is the page useful if the final report is missing?
- Does the UI keep evidence visible instead of burying it behind prose?

## 8. Backend Tests

Read:

- `apps/api/tests/test_agent_investigations.py`

Key tests:

- `test_investigation_run_produces_structured_evidence_backed_report`
- `test_investigation_start_reuses_existing_successful_run_by_default`
- `test_investigation_with_no_affected_accounts_finishes_with_uncertainty`
- `test_failed_tool_call_is_persisted_and_surfaced`

Key ideas:

- The happy-path test removes scenario labels from the incident evidence before
  launching the run, so the report cannot pass by reading the seed oracle.
- SQL evidence must include `SELECT`, parameters, result rows, and retry failure
  reasons.
- The duplicate-start test proves idempotent launch behavior.
- The ambiguous incident test proves no-account cases produce low-confidence
  uncertainty.
- The failure test monkeypatches a tool failure and verifies the failed step is
  persisted and returned from the API.

Review questions:

- Would these tests fail if synthesis used `source_scenario` as the answer?
- Would these tests fail if SQL citations were empty?
- Would these tests fail if a tool error disappeared from the run history?
- Which future tests should cover all five seeded scenarios?

## 9. Manual Smoke Check

The verified manual flow used a throwaway SQLite database and local servers:

```bash
DATABASE_URL=sqlite:////private/tmp/ops_agent_review_manual.db \
ALLOW_UNSAFE_BOOTSTRAP_SEED=true \
apps/api/.venv/bin/python -c "import app.models; from app.db.base import Base; from app.db.session import engine, SessionLocal; from app.seed import reseed_database; Base.metadata.create_all(engine); session = SessionLocal(); result = reseed_database(session); print(result.counts); session.close()"
```

```bash
cd apps/api
DATABASE_URL=sqlite:////private/tmp/ops_agent_review_manual.db \
ALLOW_UNSAFE_BOOTSTRAP_SEED=true \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

```bash
cd apps/web
API_INTERNAL_BASE_URL=http://127.0.0.1:8001 \
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 \
npm run dev -- --hostname 127.0.0.1 --port 3001
```

Checks performed:

- Opened the seeded incident page.
- Confirmed the `Run investigation` server-action form was rendered.
- Submitted the form and received a redirect to `/agent/runs/{run_id}`.
- Confirmed the report rendered root cause, affected accounts, SQL evidence,
  document citations, and tool-step history.
- Submitted the form again and confirmed it redirected to the same run.

What the final report included:

- SQL evidence for paid invoice MRR window comparison.
- SQL evidence for failed renewal invoices grouped by account.
- Document citation for `kb-runbook-billing-retry-regression`.
- Ticket citations such as `tkt_0001`.
- High confidence for the seeded billing retry incident.

## 10. Operational Gotchas From This Slice

- Do not cite SQL text without storing parameters and result rows.
- Do not let seeded `source_scenario` become the runtime answer oracle.
- Do not hide failed tool calls behind a generic failed-run status.
- Do not require at least one affected account if the product needs ambiguous
  investigations.
- Do not let repeated clicks create competing successful investigation runs.
- Do not run long-term production agent work synchronously; this V1 is only
  acceptable because tools are local and deterministic.
- Do not forget that `learning/` is ignored by `.gitignore`; force-add a guide
  only when it should be committed.

Review questions:

- Which gotchas are already protected by tests?
- Which gotchas should become eval cases in the next slice?
- Where would a background worker or polling UI change the contract?

## 11. Verification Commands

These are the commands worth understanding:

```bash
cd apps/api
./.venv/bin/python -m pytest apps/api/tests/test_agent_investigations.py -q
./.venv/bin/python -m pytest apps/api/tests -q
```

```bash
cd apps/web
npm test
npm run lint
npm run build
```

What each command proves:

- Targeted agent tests: successful report, failed tool-call surfacing,
  duplicate-run reuse, and ambiguous low-confidence behavior.
- Full backend tests: prior seed, metrics, incident, knowledge, and agent
  behavior still pass together.
- `npm test`: frontend API helper tests still pass.
- `npm run lint`: Next route type generation and TypeScript checks pass.
- `npm run build`: dashboard, incident, knowledge, and agent report routes
  compile for production.

Manual smoke proves the seeded incident can be launched through the UI path and
the final report includes both SQL-style evidence and document citations.

## 12. What To Learn Before Reviewing This Change

Focus on these topics in order:

1. Pydantic schemas as API and tool contracts.
2. SQLAlchemy JSON fields for durable run inputs, outputs, and reports.
3. Alembic migrations as the database source of truth.
4. LangGraph `StateGraph` basics: nodes, edges, state, and final output.
5. Tool-step persistence: start, success, failure, timestamps, and errors.
6. Evidence quality: SQL rows, document chunks, ticket IDs, and citations.
7. Structured report validation and confidence rules.
8. Idempotent start semantics for user-triggered workflows.
9. Next.js server actions for incident-page launch.
10. Server-rendered report pages with typed API clients.
11. Manual smoke testing when browser automation is unavailable.

If you can explain those eleven topics in this repo's code, you can review
Investigation Agent V1 for the real product risks: fake intelligence, weak
evidence, hidden failures, and audit gaps.
