import { useId, useState } from "react";
import { ingestDocument } from "../services/api";
import { ErrorAlert } from "./ErrorAlert";

const SLUG_RE = /^[a-z0-9][a-z0-9_-]*$/;

export function KnowledgeBasePanel({
  documents,
  loadingMeta = false,
  seeding = false,
  onSeedInitial,
  onIngested,
  onInspectDocument,
}) {
  const formHeadingId = useId();
  const sourceIdInputId = useId();
  const titleInputId = useId();
  const categoryInputId = useId();
  const versionInputId = useId();
  const contentInputId = useId();

  const [sourceId, setSourceId] = useState("");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("internal_operations");
  const [version, setVersion] = useState("2026.1");
  const [content, setContent] = useState("");
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const sourceInvalid =
    Boolean(touched.sourceId) && (!sourceId.trim() || !SLUG_RE.test(sourceId.trim()));
  const titleInvalid = Boolean(touched.title) && title.trim().length < 3;
  const contentInvalid = Boolean(touched.content) && content.trim().length < 20;

  async function handleSubmit(event) {
    event.preventDefault();
    setTouched({ sourceId: true, title: true, content: true });
    setStatusMessage(null);
    setErrorMessage(null);

    if (
      !SLUG_RE.test(sourceId.trim()) ||
      title.trim().length < 3 ||
      content.trim().length < 20
    ) {
      return;
    }

    setSubmitting(true);
    try {
      const res = await ingestDocument({
        source_id: sourceId.trim(),
        title: title.trim(),
        version: version.trim() || "1.0",
        category,
        content,
        force: false,
      });
      setStatusMessage(
        `Document "${res.source_id}" ${res.status} (${res.chunk_count} chunks indexed in pgvector).`,
      );
      setSourceId("");
      setTitle("");
      setContent("");
      setTouched({});
      if (onIngested) onIngested();
    } catch (err) {
      setErrorMessage({
        code: err.code || "INGEST_ERROR",
        message: err.message || "Failed to ingest SOP document.",
        requestId: err.requestId || null,
        details: err.details || null,
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="kb-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Indexed Compliance SOPs ({documents.length})</h2>
            <p className="muted-text">
              Section-chunked Markdown policies indexed with Gemini 768-dim vectors and PostgreSQL FTS.
            </p>
          </div>
        </div>

        <div className="doc-cards">
          {!loadingMeta && documents.length === 0 && (
            <div className="empty-kb-box">
              <p className="muted-text">
                No SOP documents are indexed yet. Seed the 4 bundled Card Dispute &amp; Chargeback SOPs or ingest a custom Markdown policy on the right.
              </p>
              {onSeedInitial && (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={seeding}
                  onClick={onSeedInitial}
                >
                  {seeding ? "Seeding Initial SOPs…" : "Seed Initial SOP KB"}
                </button>
              )}
            </div>
          )}

          {documents.map((doc) => (
            <article key={doc.id} className="doc-card">
              <div className="doc-card-top">
                <span className="badge badge-neutral">{doc.category}</span>
                <span className="muted-text">v{doc.version}</span>
              </div>
              <h3>{doc.title}</h3>
              <p className="muted-text">
                <code>{doc.source_id}</code> · {doc.chunk_count} chunks
              </p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() =>
                  onInspectDocument({
                    source_id: doc.source_id,
                    document_title: doc.title,
                    document_version: doc.version,
                    section_title: "All Sections",
                    chunk_id: null,
                  })
                }
              >
                Inspect Chunks
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2 id={formHeadingId}>Ingest New / Updated SOP</h2>
        <p className="muted-text">
          Idempotent SHA-256 ingestion: unchanged documents are skipped automatically without re-embedding.
        </p>

        <form
          className="sop-form"
          aria-labelledby={formHeadingId}
          onSubmit={handleSubmit}
          noValidate
        >
          <div className="field">
            <label htmlFor={sourceIdInputId}>
              Source ID <span aria-hidden="true">*</span>
            </label>
            <span id={`${sourceIdInputId}-hint`} className="field-hint">
              Lowercase slug, e.g. sop-ach-returns
            </span>
            <input
              id={sourceIdInputId}
              name="source_id"
              type="text"
              required
              pattern="^[a-z0-9][a-z0-9_-]*$"
              autoCorrect="off"
              autoCapitalize="none"
              spellCheck={false}
              aria-describedby={`${sourceIdInputId}-hint ${sourceInvalid ? `${sourceIdInputId}-err` : ""}`}
              aria-invalid={sourceInvalid ? "true" : undefined}
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, sourceId: true }))}
            />
            {sourceInvalid && (
              <span id={`${sourceIdInputId}-err`} className="field-error" role="alert">
                Use lowercase letters, numbers, hyphens, or underscores.
              </span>
            )}
          </div>

          <div className="field">
            <label htmlFor={titleInputId}>
              Document Title <span aria-hidden="true">*</span>
            </label>
            <input
              id={titleInputId}
              name="title"
              type="text"
              required
              minLength={3}
              aria-invalid={titleInvalid ? "true" : undefined}
              aria-describedby={titleInvalid ? `${titleInputId}-err` : undefined}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, title: true }))}
            />
            {titleInvalid && (
              <span id={`${titleInputId}-err`} className="field-error" role="alert">
                Title must be at least 3 characters.
              </span>
            )}
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor={categoryInputId}>Category</label>
              <select
                id={categoryInputId}
                name="category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="regulation_e">regulation_e</option>
                <option value="regulation_z">regulation_z</option>
                <option value="card_network_chargebacks">card_network_chargebacks</option>
                <option value="internal_operations">internal_operations</option>
              </select>
            </div>

            <div className="field">
              <label htmlFor={versionInputId}>Version</label>
              <input
                id={versionInputId}
                name="version"
                type="text"
                autoCorrect="off"
                spellCheck={false}
                value={version}
                onChange={(e) => setVersion(e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor={contentInputId}>
              Markdown Policy Content <span aria-hidden="true">*</span>
            </label>
            <span id={`${contentInputId}-hint`} className="field-hint">
              Use # and ## Markdown headings to preserve section citations (minimum 20 characters).
            </span>
            <textarea
              id={contentInputId}
              name="content"
              rows={6}
              required
              minLength={20}
              aria-describedby={`${contentInputId}-hint ${contentInvalid ? `${contentInputId}-err` : ""}`}
              aria-invalid={contentInvalid ? "true" : undefined}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, content: true }))}
            />
            {contentInvalid && (
              <span id={`${contentInputId}-err`} className="field-error" role="alert">
                Provide at least 20 characters of policy content.
              </span>
            )}
          </div>

          {statusMessage && (
            <p className="status-banner" role="status">
              {statusMessage}
            </p>
          )}
          <ErrorAlert
            error={errorMessage}
            onDismiss={() => setErrorMessage(null)}
          />

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Chunking & Embedding…" : "Ingest SOP into pgvector"}
          </button>
        </form>
      </section>
    </div>
  );
}
