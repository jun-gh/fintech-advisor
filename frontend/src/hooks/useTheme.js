import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "color-scheme";

function getSystemScheme() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readStoredScheme() {
  try {
    const val = localStorage.getItem(STORAGE_KEY);
    return val === "light" || val === "dark" ? val : null;
  } catch {
    return null;
  }
}

function applyMetaScheme(scheme) {
  const meta = document.querySelector('meta[name="color-scheme"]');
  if (meta) {
    meta.setAttribute("content", scheme || "light dark");
  }
}

export function useTheme() {
  const [storedScheme, setStoredScheme] = useState(() => readStoredScheme());
  const [systemScheme, setSystemScheme] = useState(() => getSystemScheme());

  const resolvedTheme = storedScheme || systemScheme;

  useEffect(() => {
    applyMetaScheme(storedScheme);
  }, [storedScheme]);

  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onSystemChange = (event) => {
      setSystemScheme(event.matches ? "dark" : "light");
    };
    media.addEventListener("change", onSystemChange);

    const onStorage = (event) => {
      if (event.key === STORAGE_KEY) {
        const next = event.newValue === "light" || event.newValue === "dark" ? event.newValue : null;
        setStoredScheme(next);
      }
    };
    window.addEventListener("storage", onStorage);

    return () => {
      media.removeEventListener("change", onSystemChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const toggleTheme = useCallback(() => {
    const currentSystem = getSystemScheme();
    const currentRendered = readStoredScheme() || currentSystem;
    const target = currentRendered === "dark" ? "light" : "dark";

    try {
      if (target === currentSystem) {
        localStorage.removeItem(STORAGE_KEY);
        setStoredScheme(null);
      } else {
        localStorage.setItem(STORAGE_KEY, target);
        setStoredScheme(target);
      }
    } catch {
      // If storage is blocked, still apply the scheme in-memory for this session
      setStoredScheme(target === currentSystem ? null : target);
    }
  }, []);

  return {
    resolvedTheme,
    isOverrideActive: storedScheme !== null,
    toggleTheme,
  };
}
