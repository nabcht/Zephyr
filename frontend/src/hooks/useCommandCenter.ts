import { useEffect, useState } from "react";

import type { CommandCenterOverview, RuntimeVerification } from "../types/api";

interface UseCommandCenterResult {
  overview: CommandCenterOverview | null;
  verification: RuntimeVerification | null;
  error: string | null;
  isLoading: boolean;
  isRefreshingMcp: boolean;
  isVerifying: boolean;
  refresh: () => Promise<void>;
  refreshMcpDiscovery: () => Promise<void>;
  verifyRuntime: () => Promise<void>;
}

async function requestJson<TResponse>(url: string, init?: RequestInit, signal?: AbortSignal): Promise<TResponse> {
  const response = await fetch(url, { ...init, signal });
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }

  return (await response.json()) as TResponse;
}

export function useCommandCenter(): UseCommandCenterResult {
  const [overview, setOverview] = useState<CommandCenterOverview | null>(null);
  const [verification, setVerification] = useState<RuntimeVerification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshingMcp, setIsRefreshingMcp] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  async function load(signal?: AbortSignal): Promise<void> {
    setIsLoading(true);
    setError(null);

    try {
      setOverview(await requestJson<CommandCenterOverview>("/api/command-center/overview", undefined, signal));
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      setError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, []);

  return {
    overview,
    verification,
    error,
    isLoading,
    isRefreshingMcp,
    isVerifying,
    refresh: async () => load(),
    refreshMcpDiscovery: async () => {
      setIsRefreshingMcp(true);
      setError(null);
      try {
        setOverview(await requestJson<CommandCenterOverview>("/api/command-center/mcp/refresh", { method: "POST" }));
      } catch (error) {
        setError(error instanceof Error ? error.message : "Unknown error");
      } finally {
        setIsRefreshingMcp(false);
      }
    },
    verifyRuntime: async () => {
      setIsVerifying(true);
      setError(null);
      try {
        setVerification(await requestJson<RuntimeVerification>("/api/command-center/verify", { method: "POST" }));
      } catch (error) {
        setError(error instanceof Error ? error.message : "Unknown error");
      } finally {
        setIsVerifying(false);
      }
    },
  };
}