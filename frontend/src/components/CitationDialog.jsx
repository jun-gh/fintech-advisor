import { useEffect, useId, useRef, useState } from "react";
import { fetchDocumentChunks } from "../services/api";

export function CitationDialog({ citation, onClose }) {
  const dialogRef = useRef(null);
  const titleId = useId();
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (citation) {
      if (!dialog.open) {
        dialog.showModal();
      }
      setLoading(true);
      setError(null);
      fetchDocumentChunks(citation.source_id)
        .then((data) => setChunks(data))
        .catch((err) => setError(err.message || "Failed to load SOP chunks."))
        .finally(() => setLoading(false));
    } else if (dialog.open) {
      dialog.close();
    }
  }, [citation]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleClose = () => {
      dialog.returnValue = "";
      onClose();
    };
    dialog.addEventListener("close", handleClose);

    // Light-dismiss fallback for browsers without <dialog closedby="any">
    let cleanupLightDismiss = () => {};
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      let pressedOutside = false;
      const isOutside = (event) => {
        const rect = dialog.getBoundingClientRect();
        return (
          event.clientX < rect.left ||
          event.clientX > rect.right ||
          event.clientY < rect.top ||
          event.clientY > rect.bottom
        );
      };
      const onPointerDown = (event) => {
        pressedOutside = isOutside(event);
      };
      const onPointerUp = (event) => {
        if (pressedOutside && isOutside(event) && dialog.open) {
          dialog.close();
        }
      };
      dialog.addEventListener("pointerdown", onPointerDown);
      dialog.addEventListener("pointerup", onPointerUp);
      cleanupLightDismiss = () => {
        dialog.removeEventListener("pointerdown", onPointerDown);
        dialog.removeEventListener("pointerup", onPointerUp);
      };
    }

    return () => {
      dialog.removeEventListener("close", handleClose);
      cleanupLightDismiss();
    };
  }, [onClose]);

  return (
    <dialog
      ref={dialogRef}
      className="citation-dialog"
      aria-labelledby={titleId}
      closedby="any"
    >
      <div className="dialog-header">
        <div>
          <p className="eyebrow">Policy Source Inspector</p>
          <h2 id={titleId} className="dialog-title">
            {citation?.document_title || "SOP Document"}
          </h2>
          {citation && (
            <p className="dialog-meta">
              <code>{citation.source_id}</code> · v{citation.document_version} ·{" "}
              {citation.section_title}
            </p>
          )}
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => dialogRef.current?.close()}
          aria-label="Close policy source dialog"
        >
          Close
        </button>
      </div>

      <div className="dialog-body">
        {loading && (
          <p className="muted-text" role="status">
            Loading SOP sections…
          </p>
        )}
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && (
          <div className="chunk-list">
            {chunks.map((chunk) => {
              const isCited = chunk.chunk_id === citation?.chunk_id;
              return (
                <article
                  key={chunk.chunk_id}
                  className={`chunk-card ${isCited ? "chunk-card-cited" : ""}`}
                >
                  <div className="chunk-card-head">
                    <strong>{chunk.section_title}</strong>
                    <span className="pill-row">
                      {isCited && <span className="badge badge-success">Cited Clause</span>}
                      <code className="chunk-id-code">{chunk.chunk_id}</code>
                    </span>
                  </div>
                  <pre className="chunk-content">{chunk.content}</pre>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </dialog>
  );
}
