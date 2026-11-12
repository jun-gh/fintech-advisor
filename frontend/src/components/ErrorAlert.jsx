const ERROR_META = {
  MODEL_RATE_LIMIT_EXCEEDED: {
    title: "AI Model Quota / Rate Limit Exceeded",
    hint: "The configured Gemini model hit its rate or quota limit. Wait a few seconds and retry.",
  },
  UPSTREAM_TIMEOUT: {
    title: "AI Model Timed Out",
    hint: "Both primary and fallback responses took too long. Try retrying your query.",
  },
  SERVICE_UNAVAILABLE: {
    title: "AI Service Temporarily Unavailable",
    hint: "The AI provider or database is experiencing temporary high load.",
  },
  UPSTREAM_AUTH_ERROR: {
    title: "AI Provider Authentication Failed",
    hint: "Check that GEMINI_API_KEY in your root .env is valid and active.",
  },
  MODEL_NOT_FOUND: {
    title: "Configured Model Not Found",
    hint: "Verify GEMINI_CHAT_MODEL / GEMINI_EMBEDDING_MODEL in your root .env.",
  },
  GUARDRAIL_BLOCKED: {
    title: "Blocked by Compliance Security Guardrail",
    hint: "Rephrase your question without system/instruction override patterns.",
  },
  VALIDATION_ERROR: {
    title: "Invalid Request Input",
    hint: "Check the highlighted fields and try again.",
  },
  NETWORK_ERROR: {
    title: "Cannot Reach Backend Server",
    hint: "Make sure FastAPI is running on port 8000 and Docker PostgreSQL is healthy.",
  },
};

export function ErrorAlert({ error, onRetry, onDismiss }) {
  if (!error) return null;

  const normalized =
    typeof error === "string"
      ? { code: "APP_ERROR", message: error, requestId: null, details: null }
      : error;

  const meta = ERROR_META[normalized.code] || {
    title: "Request Failed",
    hint: null,
  };

  const isRetryable = Boolean(normalized.details?.retryable ?? onRetry);
  const modelName = normalized.details?.model;

  return (
    <div className="error-card" role="alert" aria-live="assertive">
      <div className="error-card-head">
        <div className="pill-row">
          <span className="badge badge-danger">{normalized.code || "ERROR"}</span>
          <strong className="error-card-title">{meta.title}</strong>
        </div>
        {onDismiss && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onDismiss}
            aria-label="Dismiss error message"
          >
            Dismiss
          </button>
        )}
      </div>

      <p className="error-card-message">{normalized.message}</p>
      {meta.hint && <p className="error-card-hint">{meta.hint}</p>}

      <div className="error-card-footer">
        <span className="muted-text">
          {modelName ? `Model: ${modelName}` : ""}
          {modelName && normalized.requestId ? " · " : ""}
          {normalized.requestId ? `Request ID: ${normalized.requestId}` : ""}
        </span>

        {onRetry && isRetryable && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
            Retry Request
          </button>
        )}
      </div>
    </div>
  );
}
