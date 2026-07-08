import { listApprovalRequests } from '@/lib/api';
import { approveApprovalFromQueue, rejectApprovalFromQueue } from '@/app/actions';
import { formatDateTime, formatScenario } from '@/lib/format';

export const dynamic = 'force-dynamic';

export default async function ApprovalsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; approval_error?: string }>;
}) {
  const { status, approval_error } = await searchParams;
  const result = await listApprovalRequests(status as 'pending' | 'approved' | 'rejected' | undefined);

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Operational workspace</p>
          <h1>Approvals</h1>
        </div>
      </header>

      {approval_error ? (
        <section className="panel anomaly-panel" aria-live="polite">
          <div className="panel-message error-detail">{approval_error}</div>
        </section>
      ) : null}

      <section className="panel approval-panel">
        <div className="panel-header">
          <h2>Approval queue</h2>
          <span>{result.ok ? result.data.length : 0} total</span>
        </div>

        {!result.ok ? (
          <div className="panel-message error-detail">Failed to load approvals: {result.error}</div>
        ) : result.data.length === 0 ? (
          <div className="panel-message">No approvals found.</div>
        ) : (
          <div className="approval-stack">
            {result.data.map((approval) => (
              <article key={approval.id} className="approval-row">
                <div className="approval-row-main">
                  <div>
                    <span
                      className={`action-status action-${approval.status}`}
                    >
                      {approval.status}
                    </span>
                    <h3>{approval.action.title}</h3>
                    <p>{approval.action.description}</p>
                    <p className="approval-meta">
                      Run: {approval.run_id} · Risk: {approval.risk_level} · Requested:{' '}
                      {formatDateTime(approval.created_at)}
                    </p>
                  </div>
                  {approval.status === 'pending' ? (
                    <div className="approval-buttons">
                      <form action={approveApprovalFromQueue}>
                        <input type="hidden" name="approval_id" value={approval.id} />
                        <input
                          name="operator_token"
                          type="password"
                          className="field-input"
                          placeholder="Operator token"
                          autoComplete="off"
                        />
                        <button type="submit" className="action-button">
                          Approve
                        </button>
                      </form>
                      <form action={rejectApprovalFromQueue}>
                        <input type="hidden" name="approval_id" value={approval.id} />
                        <input
                          name="operator_token"
                          type="password"
                          className="field-input"
                          placeholder="Operator token"
                          autoComplete="off"
                        />
                        <button type="submit" className="action-button secondary-action">
                          Reject
                        </button>
                      </form>
                    </div>
                  ) : null}
                </div>
                {approval.decided_by ? (
                  <p className="approval-reason">
                    {formatScenario(approval.status)} by {approval.decided_by}
                    {approval.decided_at ? ` on ${formatDateTime(approval.decided_at)}` : ''}
                    {approval.decision_notes ? `: ${approval.decision_notes}` : ''}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
