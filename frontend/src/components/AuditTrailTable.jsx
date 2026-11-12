import { useId } from "react";

const OUTCOME_BADGE = {
  answered: "badge badge-success",
  refused: "badge badge-warning",
  blocked: "badge badge-danger",
};

export function AuditTrailTable({ logs, onRefresh }) {
  const captionId = useId();

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Immutable Compliance Audit Trail</h2>
          <p className="muted-text">
            Every copilot query is persisted with PII-redacted text, retrieved chunk IDs, outcome, and model telemetry.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={onRefresh}>
          Refresh Logs
        </button>
      </div>

      {logs.length === 0 ? (
        <p className="empty-state">No audit records yet. Run a compliance query to generate an entry.</p>
      ) : (
        <div
          tabIndex={0}
          role="region"
          aria-labelledby={captionId}
          className="table-wrapper audit-table-wrapper"
        >
          <table className="audit-table">
            <caption id={captionId} className="visually-hidden">
              Compliance copilot audit log entries
            </caption>
            <thead>
              <tr>
                <th scope="col">Request ID</th>
                <th scope="col">Sanitized Query</th>
                <th scope="col">Grounded Answer</th>
                <th scope="col">Outcome</th>
                <th scope="col">PII Masked</th>
                <th scope="col">Model</th>
                <th scope="col">Latency</th>
                <th scope="col">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((entry) => (
                <tr key={entry.id}>
                  <th scope="row">
                    <code className="mono-small">{entry.request_id.slice(0, 14)}</code>
                  </th>
                  <td data-label="Sanitized Query" className="query-cell">
                    {entry.sanitized_query}
                  </td>
                  <td data-label="Grounded Answer" className="answer-cell">
                    {entry.answer || "—"}
                  </td>
                  <td data-label="Outcome">
                    <span className={OUTCOME_BADGE[entry.outcome] || "badge"}>
                      {entry.outcome}
                    </span>
                  </td>
                  <td data-label="PII Masked">
                    {entry.pii_redacted_count > 0 ? (
                      <span className="badge badge-info">
                        {entry.pii_redacted_count} redacted
                      </span>
                    ) : (
                      <span className="muted-text">0</span>
                    )}
                  </td>
                  <td data-label="Model">
                    <code className="mono-small">{entry.model_name}</code>
                  </td>
                  <td data-label="Latency">{entry.latency_ms} ms</td>
                  <td data-label="Timestamp">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
