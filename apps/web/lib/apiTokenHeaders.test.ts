import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getAgentVersionDetail,
  publishAgentVersion,
  runEvalSuite,
  updateAgentVersion,
} from './api.ts';

type FetchCall = {
  url: string;
  init: RequestInit | undefined;
};

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function headerValue(headers: HeadersInit | undefined, key: string) {
  if (!headers) return undefined;
  if (headers instanceof Headers) return headers.get(key) ?? undefined;
  if (Array.isArray(headers)) {
    return headers.find(([name]) => name.toLowerCase() === key.toLowerCase())?.[1];
  }
  return headers[key];
}

test('protected agent version calls forward demo operator token headers', async () => {
  const calls: FetchCall[] = [];
  const originalFetch = globalThis.fetch;
  const originalInternalBaseUrl = process.env.API_INTERNAL_BASE_URL;
  process.env.API_INTERNAL_BASE_URL = 'http://api.test';
  globalThis.fetch = (async (url, init) => {
    calls.push({ url: String(url), init });
    if (String(url).endsWith('/publish')) {
      return jsonResponse({
        version: {
          id: 'version-1',
          agent_id: 'agent-1',
          status: 'published',
          version_number: 1,
          semantic_version: '1.0.0',
          published_at: '2026-07-08T00:00:00',
          published_by: 'api',
        },
      });
    }
    return jsonResponse({
      id: 'version-1',
      agent_id: 'agent-1',
      status: 'draft',
      version_number: null,
      semantic_version: null,
      system_prompt: 'Prompt',
      model: 'gpt-4o-mini',
      temperature: 0.1,
      max_tokens: 1024,
      enabled_tool_ids: ['query_revenue_metrics'],
      allowed_scopes: [],
      published_at: null,
      published_by: null,
      forked_from_version_id: null,
      created_at: '2026-07-08T00:00:00',
      updated_at: '2026-07-08T00:00:00',
    });
  }) as typeof fetch;

  try {
    await getAgentVersionDetail('agent-1', 'version-1', {
      demoOperatorToken: 'operator-secret',
    });
    await updateAgentVersion(
      'agent-1',
      'version-1',
      { system_prompt: 'Updated' },
      { demoOperatorToken: 'operator-secret' },
    );
    await publishAgentVersion('agent-1', 'version-1', {
      demoOperatorToken: 'operator-secret',
    });
  } finally {
    globalThis.fetch = originalFetch;
    process.env.API_INTERNAL_BASE_URL = originalInternalBaseUrl;
  }

  assert.equal(calls.length, 3);
  assert.deepEqual(
    calls.map((call) => headerValue(call.init?.headers, 'X-Demo-Operator-Token')),
    ['operator-secret', 'operator-secret', 'operator-secret'],
  );
});

test('eval run call forwards caller-supplied eval token header', async () => {
  const calls: FetchCall[] = [];
  const originalFetch = globalThis.fetch;
  const originalInternalBaseUrl = process.env.API_INTERNAL_BASE_URL;
  process.env.API_INTERNAL_BASE_URL = 'http://api.test';
  globalThis.fetch = (async (url, init) => {
    calls.push({ url: String(url), init });
    return jsonResponse({
      id: 'eval-run-1',
      status: 'completed',
      started_at: '2026-07-08T00:00:00',
      completed_at: '2026-07-08T00:00:00',
      total_cases: 1,
      passed_cases: 1,
      failed_cases: 0,
      accuracy: 1,
    });
  }) as typeof fetch;

  try {
    await runEvalSuite('eval-secret');
  } finally {
    globalThis.fetch = originalFetch;
    process.env.API_INTERNAL_BASE_URL = originalInternalBaseUrl;
  }

  assert.equal(calls.length, 1);
  assert.equal(headerValue(calls[0].init?.headers, 'X-Eval-Run-Token'), 'eval-secret');
});
