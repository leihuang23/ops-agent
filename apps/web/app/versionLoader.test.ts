import assert from 'node:assert/strict';
import test from 'node:test';

import {
  loadAgentVersionForPage,
  shouldRequestProtectedDetail,
} from './agents/[agentId]/versions/[versionId]/versionLoader.ts';

test('version loader falls back to summary when protected detail is rate limited', async () => {
  let detailCalls = 0;
  let summaryCalls = 0;

  const result = await loadAgentVersionForPage({
    agentId: 'revenue-ops-agent',
    versionId: 'revenue-ops-agent_v1',
    operatorToken: 'operator-token',
    shouldRequestDetail: true,
    getDetail: async () => {
      detailCalls += 1;
      return { ok: false, error: 'Version endpoint returned HTTP 429' };
    },
    getSummary: async () => {
      summaryCalls += 1;
      return {
        ok: true,
        data: {
          id: 'revenue-ops-agent_v1',
          version_number: 1,
          semantic_version: '1.0.0',
          status: 'published',
          model: 'gpt-4o-mini',
          created_at: '2026-07-08T00:00:00Z',
          published_at: '2026-07-08T00:00:00Z',
          forked_from_version_id: null,
        },
      };
    },
  });

  assert.equal(detailCalls, 1);
  assert.equal(summaryCalls, 1);
  assert.equal(result.detailUnavailableMessage, 'Version endpoint returned HTTP 429');
  assert.equal(result.versionResult.ok, true);
  assert.equal(result.versionResult.ok && result.versionResult.data.id, 'revenue-ops-agent_v1');
  assert.equal(
    result.versionResult.ok && 'system_prompt' in result.versionResult.data,
    false,
  );
});

test('version loader does not spend protected detail quota on ordinary page views', async () => {
  let detailCalls = 0;

  const result = await loadAgentVersionForPage({
    agentId: 'revenue-ops-agent',
    versionId: 'revenue-ops-agent_v1',
    operatorToken: 'operator-token',
    shouldRequestDetail: false,
    getDetail: async () => {
      detailCalls += 1;
      return {
        ok: true,
        data: {
          id: 'revenue-ops-agent_v1',
          version_number: 1,
          semantic_version: '1.0.0',
          status: 'published',
          model: 'gpt-4o-mini',
          created_at: '2026-07-08T00:00:00Z',
          published_at: '2026-07-08T00:00:00Z',
          forked_from_version_id: null,
          system_prompt: 'secret prompt',
          temperature: 0.1,
          max_tokens: 1024,
          enabled_tool_ids: ['query_revenue_metrics'],
          allowed_scopes: [],
          published_by: 'operator',
        },
      };
    },
    getSummary: async () => ({
      ok: true,
      data: {
        id: 'revenue-ops-agent_v1',
        version_number: 1,
        semantic_version: '1.0.0',
        status: 'published',
        model: 'gpt-4o-mini',
        created_at: '2026-07-08T00:00:00Z',
        published_at: '2026-07-08T00:00:00Z',
        forked_from_version_id: null,
      },
    }),
  });

  assert.equal(detailCalls, 0);
  assert.equal(result.detailUnavailableMessage, null);
  assert.equal(result.versionResult.ok, true);
});

test('protected detail is requested only after explicit edit flow events', () => {
  assert.equal(
    shouldRequestProtectedDetail({
      operatorToken: 'operator-token',
      detailUnlocked: false,
      draftSaved: false,
      publishError: null,
      versionError: null,
    }),
    false,
  );
  assert.equal(
    shouldRequestProtectedDetail({
      operatorToken: 'operator-token',
      detailUnlocked: true,
      draftSaved: false,
      publishError: null,
      versionError: null,
    }),
    true,
  );
});
