import Link from 'next/link';
import { listIncidents } from '@/lib/api';
import { formatDateTime, formatSeverityClass } from '@/lib/format';

export const dynamic = 'force-dynamic';

export default async function IncidentsPage() {
  const result = await listIncidents();

  if (!result.ok) {
    return (
      <main className="dashboard-shell">
        <section className="panel anomaly-panel">
          <div className="panel-message error-detail">
            Failed to load incidents: {result.error}
          </div>
        </section>
      </main>
    );
  }

  const incidents = result.data;

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Operational workspace</p>
          <h1>Incidents</h1>
        </div>
      </header>

      <section className="panel table-panel">
        <div className="panel-header">
          <h2>All incidents</h2>
          <span>{incidents.length} total</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Detected</th>
                <th>Affected accounts</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => (
                <tr key={incident.id}>
                  <td>
                    <Link href={`/incidents/${incident.id}`}>{incident.title}</Link>
                  </td>
                  <td>
                    <span className={`severity-pill severity-${formatSeverityClass(incident.severity)}`}>
                      {incident.severity}
                    </span>
                  </td>
                  <td>{incident.status}</td>
                  <td>{formatDateTime(incident.detected_at)}</td>
                  <td>{incident.affected_account_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
