import Link from 'next/link';

import { createAgentAction } from '@/app/actions';
import { listAgents } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { operatorMutationsEnabled } from '@/lib/operatorMutations';
import { ReadOnlyOperatorNotice } from '@/app/ReadOnlyOperatorNotice';

export const dynamic = 'force-dynamic';

const COMMON_MODELS = [
  'gpt-4o-mini',
  'gpt-4o',
  'claude-3-5-sonnet-latest',
  'claude-3-haiku-20240307',
];

function versionBadge(status: string) {
  if (status === 'published') return 'action-status action-executed';
  if (status === 'draft') return 'action-status audit-proposed';
  return 'action-status';
}

export default async function AgentsPage({
  searchParams,
}: {
  searchParams?: Promise<{ create_error?: string; created?: string }>;
}) {
  const result = await listAgents();
  const mutationsEnabled = operatorMutationsEnabled();
  const resolvedSearchParams = await searchParams;
  const createError =
    typeof resolvedSearchParams?.create_error === 'string'
      ? resolvedSearchParams.create_error
      : null;

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Control plane</p>
          <h1>Agents</h1>
          <p className="dashboard-subtitle">
            Registered agents, their published versions, and draft configurations.
          </p>
        </div>
      </header>

      {createError ? (
        <section className="panel anomaly-panel" aria-live="polite">
          <div className="panel-message error-detail">Agent creation failed: {createError}</div>
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <h2>Register a new agent</h2>
          <span>Creates the agent and a default draft version (AC-1.1)</span>
        </div>
        {!mutationsEnabled ? <ReadOnlyOperatorNotice className="report-panel-wide" /> : null}
        <form action={createAgentAction} className="form-stack">
          <label className="field-label">
            <span>Agent ID (slug, e.g. ledger)</span>
            <input
              type="text"
              name="id"
              className="field-input"
              required
              pattern="[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
              minLength={3}
              maxLength={64}
              placeholder="ledger"
              disabled={!mutationsEnabled}
            />
          </label>
          <label className="field-label">
            <span>Name</span>
            <input
              type="text"
              name="name"
              className="field-input"
              required
              maxLength={120}
              placeholder="Ledger"
              disabled={!mutationsEnabled}
            />
          </label>
          <label className="field-label">
            <span>Description (optional)</span>
            <input
              type="text"
              name="description"
              className="field-input"
              maxLength={2000}
              disabled={!mutationsEnabled}
            />
          </label>
          <label className="field-label">
            <span>Default model</span>
            <input
              type="text"
              name="default_model"
              className="field-input"
              defaultValue="gpt-4o-mini"
              list="agent-model-suggestions"
              disabled={!mutationsEnabled}
            />
            <datalist id="agent-model-suggestions">
              {COMMON_MODELS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="action-button" disabled={!mutationsEnabled} type="submit">
              Create agent
            </button>
          </div>
        </form>
      </section>

      {!result.ok ? (
        <section className="panel anomaly-panel">
          <div className="panel-message error-detail">Failed to load agents: {result.error}</div>
        </section>
      ) : result.data.agents.length === 0 ? (
        <section className="panel">
          <div className="panel-message">No agents registered.</div>
        </section>
      ) : (
        <section className="panel">
          <div className="panel-header">
            <h2>Registered agents</h2>
            <span>{result.data.total} total</span>
          </div>
          <div className="approval-stack">
            {result.data.agents.map((agent) => (
              <article key={agent.id} className="approval-row">
                <div className="approval-row-main">
                  <div>
                    <h3>
                      <Link href={`/agents/${agent.id}`} style={{ color: 'var(--blue)', textDecoration: 'none' }}>
                        {agent.name}
                      </Link>
                    </h3>
                    <p className="approval-meta">
                      <code>{agent.id}</code> · model: {agent.default_model} · {agent.version_count}{' '}
                      version{agent.version_count === 1 ? '' : 's'} · updated{' '}
                      {formatDateTime(agent.updated_at)}
                    </p>
                    {agent.description ? <p>{agent.description}</p> : null}
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                      {agent.latest_published_version ? (
                        <span className={versionBadge(agent.latest_published_version.status)}>
                          v{agent.latest_published_version.version_number} (
                          {agent.latest_published_version.semantic_version}) ·{' '}
                          {agent.latest_published_version.model} · published{' '}
                          {agent.latest_published_version.published_at
                            ? formatDateTime(agent.latest_published_version.published_at)
                            : '—'}
                        </span>
                      ) : (
                        <span className="action-status" style={{ opacity: 0.7 }}>
                          no published version
                        </span>
                      )}
                      {agent.current_draft_version ? (
                        <span className={versionBadge(agent.current_draft_version.status)}>
                          draft · {agent.current_draft_version.model}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="approval-buttons">
                    <Link
                      href={`/agents/${agent.id}`}
                      className="action-button secondary-action"
                      style={{ textDecoration: 'none' }}
                    >
                      View
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
