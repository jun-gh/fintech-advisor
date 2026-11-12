import { useCallback, useEffect, useState } from "react";
import {
  fetchAuditLogs,
  fetchDocuments,
  fetchHealth,
  seedInitialDocuments,
} from "../services/api";

export function useConfig() {
  const [health, setHealth] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [metaError, setMetaError] = useState(null);
  const [seeding, setSeeding] = useState(false);
  const [seedStatus, setSeedStatus] = useState(null);
  const [seedError, setSeedError] = useState(null);

  const refreshAll = useCallback(async () => {
    setLoadingMeta(true);
    setMetaError(null);
    try {
      const [healthData, docsData, auditData] = await Promise.all([
        fetchHealth().catch((err) => ({
          status: "degraded",
          database: "disconnected",
          pgvector: "disabled",
          error: err.message,
        })),
        fetchDocuments().catch(() => []),
        fetchAuditLogs(25).catch(() => []),
      ]);
      setHealth(healthData);
      setDocuments(docsData);
      setAuditLogs(auditData);
    } catch (err) {
      setMetaError(err.message || "Failed to load system status.");
    } finally {
      setLoadingMeta(false);
    }
  }, []);

  const refreshAudit = useCallback(async () => {
    try {
      const logs = await fetchAuditLogs(25);
      setAuditLogs(logs);
    } catch {
      // Keep previous audit state if transient fetch fails
    }
  }, []);

  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch {
      // Keep previous docs state if transient fetch fails
    }
  }, []);

  const seedKnowledgeBase = useCallback(async () => {
    setSeeding(true);
    setSeedError(null);
    setSeedStatus(null);
    try {
      const res = await seedInitialDocuments();
      await refreshDocuments();
      setSeedStatus(
        `Seeded ${res.seeded_count} initial SOP documents (${res.total_chunks} chunks indexed in pgvector).`,
      );
      return res;
    } catch (err) {
      setSeedError({
        code: err.code || "SEED_ERROR",
        message: err.message || "Failed to seed initial SOP documents.",
        requestId: err.requestId || null,
        details: err.details || null,
      });
      return null;
    } finally {
      setSeeding(false);
    }
  }, [refreshDocuments]);

  const clearSeedError = useCallback(() => {
    setSeedError(null);
  }, []);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  return {
    health,
    documents,
    auditLogs,
    loadingMeta,
    metaError,
    seeding,
    seedStatus,
    seedError,
    refreshAll,
    refreshAudit,
    refreshDocuments,
    seedKnowledgeBase,
    clearSeedError,
  };
}
