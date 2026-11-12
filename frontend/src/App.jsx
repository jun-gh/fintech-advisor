import { useEffect, useState } from "react";
import { AuditTrailTable } from "./components/AuditTrailTable";
import { CitationDialog } from "./components/CitationDialog";
import { CopilotWorkspace } from "./components/CopilotWorkspace";
import { ErrorAlert } from "./components/ErrorAlert";
import { KnowledgeBasePanel } from "./components/KnowledgeBasePanel";
import { useAgent } from "./hooks/useAgent";
import { useConfig } from "./hooks/useConfig";
import { useTheme } from "./hooks/useTheme";

const TABS = [
  { id: "copilot", label: "Compliance Copilot" },
  { id: "sops", label: "SOP Knowledge Base" },
  { id: "audit", label: "Audit Trail" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("copilot");
  const [inspectedCitation, setInspectedCitation] = useState(null);

  const {
    health,
    documents,
    auditLogs,
    loadingMeta,
    seeding,
    seedStatus,
    seedError,
    refreshAudit,
    refreshDocuments,
    seedKnowledgeBase,
    clearSeedError,
  } = useConfig();
  const { resolvedTheme, toggleTheme } = useTheme();

  const agent = useAgent({
    onComplete: () => {
      refreshAudit();
    },
  });

  const isHealthy = health?.status === "ok";
  const appName =
    health?.app_name ||
    (typeof __APP_NAME__ !== "undefined" ? __APP_NAME__ : "FintechDemo");
  const brandInitial = (appName.trim().charAt(0) || "F").toUpperCase();

  useEffect(() => {
    document.title = `${appName} — Card Dispute & Chargeback Compliance Copilot`;
  }, [appName]);

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link visually-hidden">
        Skip to main content
      </a>

      <header className="app-header">
        <div className="header-inner">
          <div className="brand-block">
            <div className="brand-mark" aria-hidden="true">
              {brandInitial}
            </div>
            <div>
              <h1 className="brand-title">{appName} Advisor</h1>
              <p className="brand-subtitle">
                Financial Compliance &amp; Policy Copilot
              </p>
            </div>
          </div>

          <div className="status-cluster">
            <span className={`badge ${isHealthy ? "badge-success" : "badge-warning"}`}>
              {isHealthy
                ? `pgvector v${health.pgvector_version || "ready"}`
                : "API / DB Checking…"}
            </span>
            <span className="badge badge-neutral">{documents.length} SOPs Indexed</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm theme-toggle-btn"
              onClick={toggleTheme}
              aria-label={
                resolvedTheme === "dark"
                  ? "Switch to light theme"
                  : "Switch to dark theme"
              }
            >
              {resolvedTheme === "dark" ? (
                <svg
                  aria-hidden="true"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
                </svg>
              ) : (
                <svg
                  aria-hidden="true"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
                </svg>
              )}
            </button>
          </div>
        </div>

        <nav className="tab-nav" aria-label="Primary">
          <ul className="tab-list">
            {TABS.map((tab) => {
              const isCurrent = activeTab === tab.id;
              return (
                <li key={tab.id}>
                  <button
                    type="button"
                    className={`tab-btn ${isCurrent ? "is-current" : ""}`}
                    aria-current={isCurrent ? "page" : undefined}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                    {tab.id === "audit" && auditLogs.length > 0 && (
                      <span className="tab-count">{auditLogs.length}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>

      <main id="main-content" className="main-content" tabIndex={-1}>
        {!loadingMeta && isHealthy && documents.length === 0 && (
          <section className="panel seed-banner" aria-label="Initial SOP setup">
            <div className="seed-banner-copy">
              <h2>Knowledge Base Is Empty</h2>
              <p className="muted-text">
                No compliance SOPs are indexed yet in PostgreSQL. Seed the 4 bundled Card Dispute &amp; Chargeback SOPs (Regulation E, Regulation Z, Visa/Mastercard Reason Codes, and Internal Ops) to get started.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              disabled={seeding}
              onClick={seedKnowledgeBase}
            >
              {seeding ? "Seeding SOPs…" : "Seed Initial SOP KB"}
            </button>
          </section>
        )}

        {seedStatus && (
          <p className="status-banner" role="status">
            {seedStatus}
          </p>
        )}

        <ErrorAlert
          error={seedError}
          onRetry={seedKnowledgeBase}
          onDismiss={clearSeedError}
        />

        {activeTab === "copilot" && (
          <CopilotWorkspace agent={agent} onInspectCitation={setInspectedCitation} />
        )}
        {activeTab === "sops" && (
          <KnowledgeBasePanel
            documents={documents}
            loadingMeta={loadingMeta}
            seeding={seeding}
            onSeedInitial={seedKnowledgeBase}
            onIngested={refreshDocuments}
            onInspectDocument={setInspectedCitation}
          />
        )}
        {activeTab === "audit" && (
          <AuditTrailTable logs={auditLogs} onRefresh={refreshAudit} />
        )}
      </main>

      <footer className="app-footer">
        <div className="footer-inner">
          <p className="footer-text">
            Card Dispute &amp; Chargeback SOP Intelligence · LangGraph + pgvector + Gemini
          </p>
        </div>
      </footer>

      <CitationDialog
        citation={inspectedCitation}
        onClose={() => setInspectedCitation(null)}
      />
    </div>
  );
}
