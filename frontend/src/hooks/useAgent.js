import { useCallback, useRef, useState } from "react";
import { streamCopilotQuery } from "../services/api";

const STAGE_ORDER = ["guardrail", "retrieve", "generate", "audit"];

export function useAgent({ onComplete } = {}) {
  const [isLoading, setIsLoading] = useState(false);
  const [activeStage, setActiveStage] = useState(null);
  const [failedStage, setFailedStage] = useState(null);
  const [completedStages, setCompletedStages] = useState([]);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const lastRequestRef = useRef(null);

  const ask = useCallback(
    async ({ query, category = null, topK = 5 }) => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
      const controller = new AbortController();
      abortRef.current = controller;
      lastRequestRef.current = { query, category, topK };

      let currentStage = "guardrail";
      setIsLoading(true);
      setError(null);
      setFailedStage(null);
      setActiveStage("guardrail");
      setCompletedStages([]);

      try {
        const finalData = await streamCopilotQuery(
          {
            query,
            category: category || null,
            top_k: topK,
          },
          {
            signal: controller.signal,
            onStage: (stage) => {
              currentStage = stage;
              setActiveStage(stage);
              setCompletedStages((prev) => {
                const idx = STAGE_ORDER.indexOf(stage);
                if (idx === -1) return prev;
                const upToCurrent = STAGE_ORDER.slice(0, idx + 1);
                return Array.from(new Set([...prev, ...upToCurrent]));
              });
            },
          },
        );

        if (finalData) {
          setResult(finalData);
          setHistory((prev) => [
            { id: finalData.request_id, query, response: finalData },
            ...prev.slice(0, 9),
          ]);
          if (onComplete) {
            onComplete(finalData);
          }
        }
        return finalData;
      } catch (err) {
        if (err.name === "AbortError") {
          return null;
        }
        setFailedStage(currentStage);
        setError({
          code: err.code || "API_ERROR",
          message: err.message || "Unable to reach Compliance Copilot.",
          requestId: err.requestId || null,
          details: err.details || null,
        });
        return null;
      } finally {
        setIsLoading(false);
        setActiveStage(null);
      }
    },
    [onComplete],
  );

  const retry = useCallback(() => {
    if (lastRequestRef.current) {
      return ask(lastRequestRef.current);
    }
    return Promise.resolve(null);
  }, [ask]);

  const clearError = useCallback(() => {
    setError(null);
    setFailedStage(null);
  }, []);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  return {
    ask,
    retry,
    cancel,
    clearError,
    isLoading,
    activeStage,
    failedStage,
    completedStages,
    result,
    setResult,
    history,
    error,
  };
}
