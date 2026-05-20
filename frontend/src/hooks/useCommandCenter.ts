import { useEffect, useState } from "react";

import type {
  CommandCenterOverview,
  MemoryBrainRepair,
  MCPConfigurationApplyRequest,
  MCPConfigurationApplyResponse,
  RuntimeVerification,
} from "../types/api";

interface UseCommandCenterResult {
  overview: CommandCenterOverview | null;
  verification: RuntimeVerification | null;
  memoryRepair: MemoryBrainRepair | null;
  error: string | null;
  isLoading: boolean;
  isRefreshingMcp: boolean;
  isApplyingMcp: boolean;
  isVerifying: boolean;
  isRepairingMemory: boolean;
  refresh: () => Promise<void>;
  refreshMcpDiscovery: () => Promise<void>;
  applyMcpConfiguration: (payload: MCPConfigurationApplyRequest) => Promise<MCPConfigurationApplyResponse>;
  verifyRuntime: () => Promise<void>;
  repairMemoryBrain: () => Promise<MemoryBrainRepair>;
}

async function requestJson<TResponse>(url: string, init?: RequestInit, signal?: AbortSignal): Promise<TResponse> {
  const response = await fetch(url, { ...init, signal });
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      try {
        const payload = (await response.json()) as { detail?: unknown; message?: unknown };
        const detail = payload.detail ?? payload.message;
        if (typeof detail === "string" && detail.trim()) {
          message = detail;
        } else if (detail !== undefined) {
          message = JSON.stringify(detail);
        }
      } catch {
        // Fall back to the status-based error message when the error payload is not JSON.
      }
    }

    throw new Error(message);
  }

  return (await response.json()) as TResponse;
}

export function useCommandCenter(): UseCommandCenterResult {
  const [overview, setOverview] = useState<CommandCenterOverview | null>(null);
  const [verification, setVerification] = useState<RuntimeVerification | null>(null);
  const [memoryRepair, setMemoryRepair] = useState<MemoryBrainRepair | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshingMcp, setIsRefreshingMcp] = useState(false);
  const [isApplyingMcp, setIsApplyingMcp] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isRepairingMemory, setIsRepairingMemory] = useState(false);

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
    memoryRepair,
    error,
    isLoading,
    isRefreshingMcp,
    isApplyingMcp,
    isVerifying,
    isRepairingMemory,
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
    applyMcpConfiguration: async (payload) => {
      setIsApplyingMcp(true);
      setError(null);
      try {
        const response = await requestJson<MCPConfigurationApplyResponse>("/api/command-center/mcp/apply", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        setOverview(response.overview);
        return response;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        setError(message);
        throw error instanceof Error ? error : new Error(message);
      } finally {
        setIsApplyingMcp(false);
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
    repairMemoryBrain: async () => {
      setIsRepairingMemory(true);
      setError(null);
      try {
        const response = await requestJson<MemoryBrainRepair>("/api/command-center/memory/repair", { method: "POST" });
        setOverview(response.overview);
        setMemoryRepair(response);
        setVerification(null);
        return response;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        setError(message);
        throw error instanceof Error ? error : new Error(message);
      } finally {
        setIsRepairingMemory(false);
      }
    },
  };
}