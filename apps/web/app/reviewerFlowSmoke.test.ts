import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

const appRoot = process.cwd();

function readWorkspaceFile(path: string) {
  return readFileSync(join(appRoot, path), 'utf8');
}

test('dashboard page exposes anomaly and navigation review surfaces', () => {
  const source = readWorkspaceFile('app/page.tsx');
  const nav = readWorkspaceFile('app/Nav.tsx');

  assert.match(source, /Detected revenue anomalies/);
  assert.match(source, /Seeded scenario coverage/);
  assert.match(source, /Recent failed invoices/);
  assert.match(source, /Ticket volume by category/);
  assert.match(nav, /href[:=]\s*['"]\/incidents['"]/);
  assert.match(nav, /href[:=]\s*['"]\/agent\/runs['"]/);
  assert.match(nav, /href[:=]\s*['"]\/approvals['"]/);
  assert.match(nav, /href[:=]\s*['"]\/knowledge['"]/);
  assert.match(nav, /href[:=]\s*['"]\/evals['"]/);
});

test('incident page exposes evidence needed before launching an investigation', () => {
  const source = readWorkspaceFile('app/incidents/[incidentId]/page.tsx');

  assert.match(source, /Run investigation/);
  assert.match(source, /Metric evidence/);
  assert.match(source, /Affected accounts/);
  assert.match(source, /Support signals/);
  assert.match(source, /Product signals/);
  assert.match(source, /Evidence sources/);
});

test('agent run page exposes report, trace, cost, citations, approvals, and step history', () => {
  const source = readWorkspaceFile('app/agent/runs/[runId]/page.tsx');

  assert.match(source, /Root cause/);
  assert.match(source, /Trace/);
  assert.match(source, /Estimated tokens/);
  assert.match(source, /Estimated cost/);
  assert.match(source, /Claim citations/);
  assert.match(source, /Cited evidence/);
  assert.match(source, /Approval queue/);
  assert.match(source, /Approve/);
  assert.match(source, /Reject/);
  assert.match(source, /Tool-step history/);
});

test('server actions forward demo operator credentials without public env exposure', () => {
  const apiSource = readWorkspaceFile('lib/api.ts');
  const actionSource = readWorkspaceFile('app/actions.ts');

  assert.match(apiSource, /X-Demo-Operator-Token/);
  assert.doesNotMatch(apiSource, /process\.env\.DEMO_OPERATOR_TOKEN/);
  assert.match(actionSource, /process\.env\.DEMO_OPERATOR_TOKEN/);
  assert.doesNotMatch(actionSource, /NEXT_PUBLIC_DEMO_OPERATOR_TOKEN/);
});

test('eval report page exposes scenario scores, failures, and traces', () => {
  const source = readWorkspaceFile('app/evals/page.tsx');

  assert.match(source, /Run Suite/);
  assert.match(source, /Scenario results/);
  assert.match(source, /Expected/);
  assert.match(source, /Actual/);
  assert.match(source, /Observed evidence/);
  assert.match(source, /failure_reasons/);
  assert.match(source, /Trace/);
});
