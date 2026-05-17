import { useEffect, useState } from "react";

import type { RuntimeActionStreamEvent, RuntimePreparationResponse, SystemStatus } from "../types/api";

type RuntimeActionName = "reload" | "prepare";

interface UseSystemStatusResult {
  status: SystemStatus | null;
  error: string | null;
  isLoading: boolean;
  isReloading: boolean;
  isPreparing: boolean;
  prepareResult: RuntimePreparationResponse | null;
  runtimeActivity: RuntimeActionStreamEvent | null;
  refresh: () => Promise<void>;
  reloadRuntime: () => Promise<void>;
  prepareRuntime: () => Promise<void>;
}

async function requestStatus(url: string, init?: RequestInit, signal?: AbortSignal): Promise<SystemStatus> {
  const response = await fetch(url, { ...init, signal });
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }

  return (await response.json()) as SystemStatus;
}

function createRuntimeActivity(
  action: RuntimeActionName,
  stage: string,
  message: string,
  options?: {
    done?: boolean;
    success?: boolean | null;
  },
): RuntimeActionStreamEvent {
  const done = options?.done ?? false;
  const success = options?.success ?? null;

  return {
    action,
    stage,
    message,
    lines: [message],
    done,
    success,
    status: null,
  };
}

function buildRuntimeActivityError(
  action: RuntimeActionName,
  message: string,
  current: RuntimeActionStreamEvent | null,
): RuntimeActionStreamEvent {
  if (current && current.action === action) {
    return {
      ...current,
      stage: "error",
      message,
      lines: [...current.lines, message],
      done: true,
      success: false,
    };
  }

  return createRuntimeActivity(action, "error", message, { done: true, success: false });
}

async function streamRuntimeAction(
  url: string,
  onEvent: (event: RuntimeActionStreamEvent) => void,
): Promise<RuntimeActionStreamEvent | null> {
  const response = await fetch(url, { method: "POST" });
  if (!response.ok || response.body === null) {
    throw new Error(`Request failed with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalEvent: RuntimeActionStreamEvent | null = null;

  function processEventBlock(block: string): void {
    const lines = block.split(/\r?\n/);
    let eventName = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    if (dataLines.length === 0) {
      return;
    }

    const payload = JSON.parse(dataLines.join("\n")) as RuntimeActionStreamEvent;
    if (eventName === "snapshot" || eventName === "done") {
      onEvent(payload);
      if (eventName === "done") {
        finalEvent = payload;
      }
      return;
    }

    if (eventName === "error") {
      throw new Error(payload.message || "Runtime action failed.");
    }
  }

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);
      if (block) {
        processEventBlock(block);
      }
      boundary = buffer.indexOf("\n\n");
    }

    if (done) {
      const trailing = buffer.trim();
      if (trailing) {
        processEventBlock(trailing);
      }
      break;
    }
  }

  return finalEvent;
}

export function useSystemStatus(): UseSystemStatusResult {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeAction, setActiveAction] = useState<RuntimeActionName | null>(null);
  const [prepareResult, setPrepareResult] = useState<RuntimePreparationResponse | null>(null);
  const [runtimeActivity, setRuntimeActivity] = useState<RuntimeActionStreamEvent | null>(null);

  async function load(signal?: AbortSignal): Promise<void> {
    setIsLoading(true);
    setError(null);

    try {
      setStatus(await requestStatus("/api/system/status", undefined, signal));
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
    status,
    error,
    isLoading,
    isReloading: activeAction === "reload",
    isPreparing: activeAction === "prepare",
    prepareResult,
    runtimeActivity,
    refresh: async () => load(),
    reloadRuntime: async () => {
      if (activeAction !== null) {
        return;
      }

      setActiveAction("reload");
      setError(null);
      setRuntimeActivity(createRuntimeActivity("reload", "queued", "Reload requested from the React control room."));
      try {
        const finalEvent = await streamRuntimeAction("/api/runtime/reload/stream", (event) => {
          setRuntimeActivity(event);
          if (event.status) {
            setStatus(event.status);
          }
        });
        if (!finalEvent) {
          throw new Error("Runtime reload finished without a completion event.");
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        setError(message);
        setRuntimeActivity((current) => buildRuntimeActivityError("reload", message, current));
      } finally {
        setActiveAction(null);
      }
    },
    prepareRuntime: async () => {
      if (activeAction !== null) {
        return;
      }

      setActiveAction("prepare");
      setError(null);
      setPrepareResult(null);
      setRuntimeActivity(createRuntimeActivity("prepare", "queued", "Prepare requested from the React control room."));
      try {
        const finalEvent = await streamRuntimeAction("/api/runtime/prepare/stream", (event) => {
          setRuntimeActivity(event);
          if (event.status) {
            setStatus(event.status);
          }
        });
        if (!finalEvent || finalEvent.status === null) {
          throw new Error("Runtime preparation finished without a completion event.");
        }

        setPrepareResult({
          success: finalEvent.success ?? false,
          lines: finalEvent.lines,
          status: finalEvent.status,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        setError(message);
        setRuntimeActivity((current) => buildRuntimeActivityError("prepare", message, current));
      } finally {
        setActiveAction(null);
      }
    },
  };
}
