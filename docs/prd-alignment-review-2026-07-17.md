# PRD Alignment Review — Project 1 and Project 2 (2026-07-17)

Reviewer: Kimi Code CLI (fresh review, all evidence re-verified on 2026-07-17)
Scope: Project 1 against `prd.md`; Project 2 (Agent Control Plane and Evaluation Studio)
against `local-docs/project-2/PRD.md`. Branch `main` @ `c1c22d4`.
Supersedes: `docs/prd-alignment-review.md` and `docs/prd-alignment-review-2026-07-07.md`
(Project 1 only; both predate the Project 2 control plane).

## 1. Executive summary

Both projects are **substantially PRD-compliant and behave correctly under live testing**.

- **Project 1**: all 5 PRD success criteria verified live (seed scenarios, eval pass rate,
  cited evidence, approval gating, per-run trace/steps/cost). All 12 core API routes and all
  14 data models exist. The single hard deviation is the frontend stack: **Tailwind CSS and
  shadcn/ui are not used at all** — the UI is hand-written CSS (`apps/web/app/globals.css`).
- **Project 2**: all 21 functional requirements (FR-1..FR-21) are implemented, with four
  deliberate, documented tightenings that diverge from the PRD's literal wording (closed tool
  catalog, v1 permission carve-outs, NOT-NULL `agent_version_id`, virtualized
  `eval_results.trace_url`). All 9 success metrics (S-1..S-9) have test and/or live evidence.
  Non-functional posture (perf, reliability, security, auditability) is strong; findings are
  minor and listed in §6.

One **environment-caused outage** was found and diagnosed on the reviewer's own machine: the
existing `postgres_data` Docker volume was stamped at Alembic revision `20260710_0016` by a
*different* branch's migration of the same id, so `alembic upgrade head` is a no-op and the
API crash-loops at bootstrap (`tools.created_at does not exist`). This is not a defect in
`main`'s code — a fresh database migrates and boots cleanly — but it exposes a real
operational robustness gap (no startup schema-drift detection). See F-1 and R-1/R-2.

## 2. How this review was conducted

1. **Static audit**: both PRDs read in full; every requirement mapped to code with
   file:line evidence (routers, services, models, migrations, seed, tests, frontend).
2. **Test suites (fresh runs)**:
   - Backend: `apps/api/.venv/bin/python -m pytest` → **381 passed, 2 skipped** (the 4
     `test_health.py` failures seen without infrastructure are environment-dependent — they
     require live Postgres/Redis on localhost and pass once Docker is up).
   - Frontend: `npm test` → **15 passed**; `npm run lint` (typegen + `tsc --noEmit`) → clean;
     `npm run build` → clean (all 20 routes compile).
   - Ruff: all checks passed.
   - Opt-in perf: `RUN_DASHBOARD_PERF=1` 10k-run dashboard benchmark → **43.7 ms** (target
     ≤ 500 ms); read-endpoint perf test → passed.
   - Playwright (live stack, Chromium): **8 passed, 1 skipped** (the read-only-demo spec is
     conditional on `OPERATOR_UI_ENABLED=false`). The one initial failure was a harness
     setup issue — demo mode requires `DEMO_OPERATOR_TOKEN` in the spec environment; with it
     exported, the spec passes in ~1 s.
3. **Live verification** on the full Docker stack (`APP_ENV=demo`, tokens set) against a
   scratch database (`ledger_review`; the user's drifted volume was left untouched —
   see F-1). Seed counts confirmed canonical: 60 accounts, 300 users, 60 subscriptions,
   600 invoices, 6000 product events, 240 tickets, 24 knowledge docs, 6 incidents, 6 eval
   cases, 1 agent, 5 agent versions, 7 tools, 1 eval dataset.

## 3. Project 1 vs `prd.md`

### 3.1 Success criteria (PRD lines 90–96) — all verified live

| Criterion | Status | Fresh evidence |
|---|---|---|
| ≥5 seeded incident scenarios | ✅ | 6 scenarios incl. ambiguity case (`inc_eval_unknown_root_cause`); `app/seed.py:56-152` |
| ≥4/5 eval root-cause accuracy | ✅ | CLI `python -m app.evals.runner --json` → **6/6 passed**, all scores 1.0 (v1 default path); dataset runs: phase6 **6/6**, degraded **5/6** |
| Every final report cites SQL/tickets/docs | ✅ | Live investigation returned evidence kinds `sql`, `document`, `ticket`; typed `ReportEvidence` with `source_query` + citation rows; scored by `score_citation_quality` |
| Risky actions blocked until approved | ✅ | Live: 2 low-risk actions `executed`, 2 high-risk `pending_approval`; approve → `executed` with `decided_by`; reject → `rejected` (terminal); double-decision → **409** |
| Every run has trace, step log, token/cost, final report | ✅ | Live run: 9 ordered steps, `trace_url` (local fallback), `prompt_tokens`/`completion_tokens`/`cost_estimate_usd` populated, final report present |

### 3.2 Recommended stack (PRD lines 1–14)

All present **except Tailwind + shadcn/ui**:

- ✅ Next.js 16 + TypeScript; FastAPI; Pydantic v2; SQLAlchemy 2; Alembic (16 migrations);
  Postgres + pgvector (HNSW index, real cosine search); Redis (cache, rate limiter, Celery
  broker); LangGraph `StateGraph` (`app/agent/workflow.py:335-343`); provider-neutral
  tracing with Langfuse/LangSmith/local fallback (`app/agent/tracing.py`); Celery
  (soft 540 s / hard 600 s limits + beat reaper); OpenAI-first LLM layer with Anthropic
  abstraction and Noop fallback; pytest (381 tests) + Playwright (6 specs) + DB-persisted
  eval cases; Docker Compose + Render + Vercel configs.
- ❌ **Tailwind CSS / shadcn/ui absent** (finding F-4): no `tailwindcss`/Radix dependency,
  no config, no `components/ui`. Styling is ~1300 lines of hand-written CSS. The UI works
  and all pages render, but the PRD's stated frontend stack is not implemented.

### 3.3 Data models and API routes

- All 14 PRD data models exist in `apps/api/app/models.py` with migrations (plus 8
  additional Project-2 tables).
- All 12 core routes exist and are contract-tested (`tests/test_prd_api_contract.py`);
  ~25 additional routes from Project 2 (additive, per NFR-6).
- Token gating per `AGENTS.md` verified **live** in demo mode: `POST /agent/investigations`,
  `/evals/run`, `/runs`, `/agents`, `/tools`, `/eval-datasets`, `/approvals/{id}/approve`
  all return **403 without a token**; gates use `secrets.compare_digest` and fail closed
  (`app/core/access.py:24-46`).

### 3.4 Project 1 deviations and caveats

| # | Item | Assessment |
|---|---|---|
| F-4 | Tailwind/shadcn missing (PRD line 3) | Only hard PRD deviation. Either adopt the stack or amend the PRD. |
| C-1 | Eval pass bar is deterministic | With default `LLM_PROVIDER=none`, root causes come from a keyword classifier and scoring is exact-match; the 4/5 criterion never exercises an LLM. Consistent with "determinism first" guardrails, but reviewers should know what is (not) being measured. |
| C-2 | Failed runs persist `final_report=None` (`evals/runner.py:355-379`) | Literal reading of "every run has a final report" fails on error paths; consistent with the failure-visibility rule. Acceptable, documented. |
| C-3 | `EVAL_RUN_TOKEN` / `DOCUMENT_INGEST_TOKEN` fail closed in **all** envs when unset | Stricter than AGENTS.md's "local/test can run without tokens" (which holds only for `DEMO_OPERATOR_TOKEN`). Security-positive; docs should say so. |
| C-4 | `cited_evidence` has no schema `min_length` | Non-emptiness is workflow- and eval-score-enforced, not schema-enforced. Minor hardening opportunity. |
| C-5 | AGENTS.md drift | Says the LangGraph graph is "compiled once at startup" — it is compiled per run (`workflow.py:343`); the backend-domain list omits `agents`, `tools`, `runs`, `dashboard`. |

## 4. Project 2 vs `local-docs/project-2/PRD.md`

### 4.1 Functional requirements — all implemented

| FR | Status | Evidence (fresh where noted) |
|---|---|---|
| FR-1 Agent registry | ✅ | `POST /agents` 201, kebab-case slug validated (live 422 on bad slug), duplicate → 409; list includes draft/published summaries |
| FR-2 Versioning draft/publish | ✅ | Fork-from-version works live; publish assigns monotonic `version_number` (v3 observed) + `N.0.0` semver; unique partial index on published `(agent_id, version_number)` |
| FR-3 Immutability | ✅ | **Live: PATCH published → 409; re-publish → 409**; runtime rejects non-published versions at creation and at executor claim |
| FR-4 Tool registry | ✅ with deviation D-1 | 7 built-ins live with I/O schemas + scopes; `POST /tools` rejects anything outside the built-in catalog (422) — stricter than the PRD's generic wording |
| FR-5 Scope enum | ✅ | 4 scopes; DB CHECK constraint `ck_tools_permission_scope` (migration 0016) |
| FR-6 Tool binding (id ∧ scope) | ✅ with deviation D-2 | Policy `can_call_tool` enforced before dispatch; **deliberate v1 carve-outs** (`agent/service.py:819-844`, `evals/router.py:80-89`) let the pinned v1 snapshot use action tools / legacy eval path by scope alone |
| FR-7 Blocked-call visibility | ✅ | **Live**: eval run against a version with `run_eval` stripped → 403 + `X-Agent-Run-Id`; that run is `failed` with step `run_eval / blocked_reason=tool_not_enabled` |
| FR-8 Run creation | ✅ | **Live**: `POST /runs` → 202, Celery dispatch, `queued` status returned |
| FR-9 Lifecycle | ✅ | **Live**: `queued → running → waiting_for_approval → succeeded` observed; approvals resumed the run; illegal transitions → 409 (`/runs/{id}/transitions`) |
| FR-10 Step persistence | ✅ | Live run showed 9 ordered steps with tools/status; unique `(run_id, sequence)` |
| FR-11 Staleness self-heal | ✅ | Soft-limit → `failed` with `soft_time_limit_exceeded` (control-plane path); beat reaper every 60 s observed running in worker logs; tests cover both. See F-6 for a string-drift nit and F-7 for the eval-task asymmetry |
| FR-12 Platform-wide approvals | ✅ | **Live**: `GET /approvals?agent_version_id=…&risk_level=…` filters work |
| FR-13 Action safety invariants | ✅ | **Live**: approve→executed+`decided_by`; reject→rejected terminal; double-decision→409 |
| FR-14 Eval dataset CRUD | ✅ | `mrr-drop-suite` seeded with all 6 cases; create/list/get tested |
| FR-15 Dataset run vs version | ✅ | **Live**: 202 + async Celery execution; unpublished → 404; no-permission → 403 with audit |
| FR-16 Result persistence | ✅ | **Live**: per-case `root_cause_score`, `citation_quality_score`, `action_safety_score`, `latency_ms`, `cost_estimate_usd`, `trace_url`, `failure_reasons`, `example_output`; filters by version/dataset work |
| FR-17 Version comparison | ✅ | **Live**: `compare?version_a=phase6&version_b=phase6_degraded` → pass rates 1.0 vs 0.8333 and `regressions: [eval_usage_drop_after_import_outage]`; UI has regression banner + row highlighting |
| FR-18 Per-run observability | ✅ | Run detail exposes status, version, input payload, steps w/ per-step `model_usage`, trace link, tokens, cost, final report |
| FR-19 Aggregate dashboard | ✅ | **Live**: `/dashboard/agents/ledger` returns per-version runs, success rate, avg/p95 latency, avg/total cost, last run |
| FR-20 Model usage tracking | ✅ | `model_usage` table; per-step attribution via `AgentRunStep.model_usage_id` (plain column, not FK — documented) |
| FR-21 Token gating | ✅ | **Live 403s** on every new mutating route without token; dual operator/eval token accepted on dataset runs; fail-closed + `compare_digest` |

### 4.2 Data models (§9) and seeds (§9.5)

- All §9 tables/columns present (migrations 0010–0016), including the unique partial index
  and the tools CHECK constraint. Documented deviations: `agent_runs.agent_version_id` is
  NOT NULL (stricter than §9.2's "nullable"); `eval_results.trace_url` is surfaced via the
  parent run rather than a column; `tool_permissions` normalization intentionally omitted
  per the PRD's own v1 recommendation.
- Seeds verified live: `ledger` + published `ledger_v1` (4 tools,
  3 scopes), `ledger_phase6` (7 tools, 4 scopes), intentionally degraded
  `ledger_phase6_degraded` (`search_docs` removed, negative version number), and
  `mrr-drop-suite` with 6 cases.

### 4.3 Success metrics (§11)

S-1..S-9 all verified — by the live checks above (S-1, S-2, S-3, S-4, S-5, S-6, S-8 infra)
and the backend/Playwright suites (S-7 citation assertions, S-9 Project 1 suite passes
unchanged). Quantitative targets: read p95 live sample `/agents 9.5 ms, /tools 4.3 ms,
/runs 8.9 ms, /dashboard/agents 4.5 ms, /eval-datasets 3.5 ms` (target ≤ 300 ms); 10k-run
dashboard aggregate **43.7 ms** (target ≤ 500 ms); good-version eval pass 6/6 (target ≥4/5);
degraded 5/6 with a flagged regression; eval suite wall time well under the 90 s target.

### 4.4 NFRs (§7)

- **NFR-1 perf**: verified (above). Note F-8: dashboard percentiles are computed in Python
  over all timestamped runs (deliberate Postgres/SQLite portability trade-off,
  `dashboard/service.py:108-134`) — fine at the 10k NFR target, revisit beyond it.
- **NFR-2 reliability**: reaper + soft-limit handling verified; no runs stuck in
  `running`/`queued`/`waiting_for_approval` after the live session. See F-7.
- **NFR-3 security**: gates fail closed (live); permission enforcement is runtime, not UI;
  `OBSERVABILITY_FULL_PAYLOADS=false` default with metadata-only trace payloads; no secrets
  in responses; slowapi rate limits on all mutation/search routes (note F-9 on defaults).
  `OPERATOR_UI_ENABLED` fail-closed server-action guard on the web side.
- **NFR-4 auditability**: the three-run DB-only audit practice from the phase-6 signoff was
  reproduced in spirit — live runs reconstruct fully from `agent_runs` + `agent_run_steps` +
  `mock_actions` + `approval_requests` + `action_audit_events`.
- **NFR-5/6 maintainability/compatibility**: per-domain layout followed; migrations additive
  and reversible with cycle tests; Project 1 surfaces pass unchanged.
- **NFR-7/8 observability/usability**: structured error envelope for domain errors,
  sanitized `X-Request-ID` (verified live), JSON logging; demo route completes in minutes.

## 5. Correctness issues found during testing

1. **None blocking.** Every PRD behavior exercised live behaved as specified. The only test
   failures encountered were environmental (health tests without infra; Playwright spec
   without `DEMO_OPERATOR_TOKEN` exported) and both pass under the documented setup.
2. **Observation (not a defect):** anonymous-route 404s use FastAPI's default
   `{"detail": "Not Found"}` body rather than the app's structured error envelope; domain
   404s do use descriptive messages. If the envelope is meant to be universal (NFR-7), add a
   catch-all handler.

## 6. Findings register (gaps, deviations, robustness)

| ID | Severity | Area | Finding |
|---|---|---|---|
| F-1 | **High (ops)** | Reliability | Existing `postgres_data` volume is stamped `20260710_0016` by branch `codex/fix-project2-prd-gaps`'s *different* migration of the same id; `alembic upgrade head` on `main` is then a silent no-op and the API crash-loops (`tools.created_at does not exist`). Revision-id collision across branches + no startup schema-drift detection. Fresh DBs are unaffected (verified: 0001→0016 applies cleanly). |
| F-2 | Medium | Reliability | `evals/tasks.py` has no task-level `SoftTimeLimitExceeded` catch (unlike `agent/tasks.py` / `runs/tasks.py`); a timed-out eval suite shows `running` until the read-path self-heal flips it (up to ~14 min: 540 s limit + 300 s grace). |
| F-3 | Low | Consistency | Timeout reason strings differ: legacy path `"celery soft time limit exceeded"` vs control-plane `"soft_time_limit_exceeded"` (FR-11's literal string matches only the new path). |
| F-4 | Medium | PRD compliance | Tailwind CSS and shadcn/ui (PRD line 3) are not implemented; hand-written CSS instead. |
| F-5 | Low | Policy purity | FR-6 "iff" is weakened for the pinned v1 snapshot (deliberate compat carve-outs) — documented in code and tests, but a reviewer reading FR-6 literally should know. |
| F-6 | Low | PRD text | `POST /tools` is a closed catalog (422 for non-built-ins) — stricter than FR-4's wording; PRD §10 also omits the shipped `PATCH /agents/{id}/versions/{vid}` and `POST /runs/{id}/transitions` routes. |
| F-7 | Low | Docs/config | Code defaults for rate limits are 1000/min; `.env.example`/runbook set 10/min mutations, 60/min search. Behavior is env-dependent as designed, but the gap is worth a doc note. |
| F-8 | Low | Scale | Dashboard p95/avg latency computed in Python over all timestamped runs; acceptable at 10k (43.7 ms measured), not set-based. |
| F-9 | Low | Coverage | No end-to-end test that `OBSERVABILITY_FULL_PAYLOADS=false` withholds payloads from a *hosted* provider (isolation-only; carried over from the 07-07 review). |
| F-10 | Info | Schema | `cited_evidence` non-emptiness is workflow-enforced, not schema-enforced (no `min_length`). |

## 7. Recommendations

Priority order; R-1/R-2 address the only issue that actually broke a running system.

- **R-1 (do now) — Repair the drifted local volume** so plain `docker-compose up` works
  again. From `apps/api` inside a one-off container:
  `alembic stamp 20260710_0015 && alembic upgrade head` (applies main's real 0016), then
  restart the API. Do **not** use `down -v` unless a full reseed is acceptable.
- **R-2 — Prevent recurrence**: never reuse an Alembic revision id for different content
  across branches (treat ids as immutable once pushed; the stale worktree branch
  `codex/fix-project2-prd-gaps` should be deleted or rebased to rename its 0016). Add a
  startup check — `alembic check` or a cheap "model columns vs information_schema" sanity
  probe — so schema drift fails fast with a clear message instead of an ORM crash deep in
  bootstrap.
- **R-3 — Resolve F-4 one way or the other**: either adopt Tailwind + shadcn/ui for new UI
  work (incremental adoption is fine) or amend `prd.md` line 3 to "hand-rolled CSS with
  design tokens" so the contract matches reality. Per AGENTS.md, update PRD and AGENTS.md
  together.
- **R-4 — Add the eval-task soft-limit catch** (`evals/tasks.py`): mirror
  `agent/tasks.py:31-49` so timed-out eval suites flip to `failed` immediately with the
  reason recorded, instead of relying on read-path self-heal (F-2). Unify the reason string
  while there (F-3).
- **R-5 — Sync docs with shipped behavior**: add the two extra routes to Project 2 PRD §10;
  note the closed tool catalog (FR-4) and v1 carve-outs (FR-6) explicitly; fix AGENTS.md's
  "compiled once at startup" and its backend-domain list; document the all-envs fail-closed
  behavior of the eval/ingest tokens (C-3) and the rate-limit default gap (F-7).
- **R-6 — Small hardening (optional)**: `min_length=1` on `cited_evidence` (F-10); a hosted
  redaction e2e behind provider credentials (F-9); a catch-all 404 through the structured
  error envelope (§5.2); a SQL-side percentile for the dashboard once run volume grows well
  past 10k (F-8).

## 8. Reproduction notes for this review's live session

- Stack was run as: `APP_ENV=demo DEMO_OPERATOR_TOKEN=… EVAL_RUN_TOKEN=…
  DOCUMENT_INGEST_TOKEN=… DATABASE_URL=postgresql+psycopg://ledger:ledger@postgres:5432/ledger_review
  docker-compose up -d`, after one-off seeding via
  `docker-compose run --rm -e ALLOW_UNSAFE_BOOTSTRAP_SEED=true api python -m app.bootstrap`
  (the seed allowlist in `seed.py:1278-1295` correctly refused the non-standard DB name
  until the explicit override — guard verified working).
- The user's original `ledger` database was not modified by this review.
- Playwright in demo mode needs `DEMO_OPERATOR_TOKEN` exported for the API-driving specs.

---

## 9. Remediation log (2026-07-17, same day)

The recommendations in §7 were implemented. All changes verified: backend **390 passed /
2 skipped** (was 381/2; +9 new tests), Ruff clean, frontend 15/15 + typecheck clean, and a
fresh live pass on the rebuilt Docker stack.

| Rec | Status | What changed |
|---|---|---|
| R-1 | ✅ Done | Volume repaired in place: `alembic stamp 20260710_0015` + `alembic upgrade head` applied main's real 0016 (tools timestamps + CHECK constraint). **Second drift layer found during re-verification**: the divergent branch's 0016 had also left stray objects — an `eval_runs` table, an FK `fk_eval_results_eval_run_id_eval_runs` (broke every eval-result insert with `ForeignKeyViolation`), a stray unique constraint, and `agent_run_steps.telemetry_error`. Removed with the branch's own downgrade operations (`DROP CONSTRAINT` ×2, `DROP TABLE eval_runs`, `DROP COLUMN telemetry_error`). Dataset eval then passed 6/6 live on the repaired volume. Stack runs healthy on the default config. |
| R-2 | ✅ Done | New `app/db/schema_check.py`: bootstrap now probes the startup-critical tables/columns after migrations and fails fast with an actionable message naming the missing object and the stamp/upgrade repair, instead of crashing in ORM code. 3 new tests (`test_bootstrap.py`). Limitation: detects *missing* objects only — the stray-FK case above is out of scope by design (extra objects must not fail startup, since a DB legitimately newer than the code would then refuse to boot). |
| R-3 | ✅ Done | Per user decision, `prd.md` line 3 now records the shipped stack (hand-rolled CSS with design tokens) with a dated revision note, instead of retrofitting Tailwind/shadcn. Also per user decision, the stale branch `codex/fix-project2-prd-gaps` (tip `190f621`, owner of the colliding 0016) was deleted and its dead worktree registration pruned, removing the revision-collision source. |
| R-4 | ✅ Done | `evals/tasks.py` now catches `SoftTimeLimitExceeded`, persists terminal `soft_time_limit_exceeded` failure markers for unfinished cases (new `record_eval_suite_timeout` in `evals/runner.py`), and re-raises; completed cases are untouched (one row per case). Reason string unified to `soft_time_limit_exceeded` across legacy and control-plane paths (F-3). 3 new tests (`test_celery_timeout.py`). |
| R-5 | ✅ Done | Project 2 PRD: FR-4 closed-catalog note, FR-6 v1 carve-out note, §10 gains `PATCH /agents/{id}/versions/{vid}` and `POST /runs/{id}/transitions`. AGENTS.md: domain list completed (`agents`, `dashboard`, `runs`, `tools`), LangGraph "compiled once at startup" corrected to per-run, token-gate paragraph now states eval/ingest gates fail closed in all envs. `docs/security.md`: rate-limit values are env-driven (code default 1000/min; `.env.example` 10/60). |
| R-6 | ✅ Done (3 of 4) | `cited_evidence` now `Field(min_length=1)` + schema test + one fixture fixed. Unmatched-route 404s use the structured envelope (`not_found` + request_id); domain 404s keep their `{"detail": ...}` contract (2 new tests). **Deferred**: hosted redaction e2e (needs real provider credentials — F-9 remains isolation-only) and SQL-side dashboard percentile (F-8 — current approach measured 43.7 ms at 10k runs; revisit beyond that scale). |

New follow-up recorded during remediation: the drifted volume carried *two* layers of
damage (missing main-migration objects **and** stray branch-migration objects). The stamp
+upgrade fixed the first; only live re-verification surfaced the second. If full-fidelity
schema parity ever matters more than this volume's history, a fresh reseed
(`down -v && up`) remains the clean path.
