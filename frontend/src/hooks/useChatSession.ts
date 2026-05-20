import { useEffect, useRef, useState } from "react";

import type {
  ChatTurnRequest,
  ChatStreamEvent,
  SessionAttachment,
  SessionAttachmentListResponse,
  SessionCreateResponse,
  SessionHistoryResponse,
  SessionMessage,
} from "../types/api";

const SESSION_STORAGE_KEY = "uzephyr.activeSessionId";

interface UseChatSessionResult {
  sessionId: string | null;
  messages: SessionMessage[];
  attachments: SessionAttachment[];
  error: string | null;
  isBootstrapping: boolean;
  isSending: boolean;
  isRunningMission: boolean;
  isUploadingAttachments: boolean;
  deletingAttachmentId: string | null;
  createSession: () => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  runMission: (message: string) => Promise<void>;
  uploadAttachments: (files: File[]) => Promise<void>;
  deleteAttachment: (attachmentId: string) => Promise<void>;
}

function requestSensitiveToolApproval(mode: "chat" | "mission"): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  const actionLabel = mode === "mission" ? "mission" : "chat turn";
  return window.confirm(
    `Safety confirmation is enabled for the web interface. Allow sensitive tools during this ${actionLabel}?\n\nChoose Cancel to continue with sensitive tools blocked for this request.`,
  );
}

async function requestJson<TResponse>(url: string, init?: RequestInit): Promise<TResponse> {
  const response = await fetch(url, init);
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
        // Fall back to the status-based message.
      }
    }

    throw new Error(message);
  }

  return (await response.json()) as TResponse;
}

async function postJson<TResponse>(url: string, body?: unknown): Promise<TResponse> {
  return requestJson<TResponse>(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function getJson<TResponse>(url: string): Promise<TResponse> {
  return requestJson<TResponse>(url);
}

async function uploadAttachment<TResponse>(url: string, file: File): Promise<TResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return requestJson<TResponse>(url, {
    method: "POST",
    body: formData,
  });
}

function storeSessionId(sessionId: string | null): void {
  if (typeof window === "undefined") {
    return;
  }

  if (sessionId) {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    return;
  }

  window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
}

function readStoredSessionId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.sessionStorage.getItem(SESSION_STORAGE_KEY);
}

function upsertAssistantSnapshot(current: SessionMessage[], content: string): SessionMessage[] {
  const next = [...current];
  const assistant = { role: "assistant", content } as const;
  const lastMessage = next[next.length - 1];
  if (lastMessage?.role === "assistant") {
    next[next.length - 1] = assistant;
    return next;
  }

  next.push(assistant);
  return next;
}

async function streamTurn(
  url: string,
  payload: ChatTurnRequest,
  onSnapshot: (content: string) => void,
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || response.body === null) {
    throw new Error(`Request failed with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

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

    const payload = JSON.parse(dataLines.join("\n")) as ChatStreamEvent;
    if (eventName === "snapshot") {
      onSnapshot(payload.content);
      return;
    }

    if (eventName === "error") {
      throw new Error(payload.content || "Streaming chat failed.");
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
}

export function useChatSession(safetyConfirmationRequired: boolean): UseChatSessionResult {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [attachments, setAttachments] = useState<SessionAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [pendingMode, setPendingMode] = useState<"chat" | "mission" | null>(null);
  const [isUploadingAttachments, setIsUploadingAttachments] = useState(false);
  const [deletingAttachmentId, setDeletingAttachmentId] = useState<string | null>(null);
  const mountedRef = useRef(true);

  async function loadSessionHistory(activeSessionId: string): Promise<SessionMessage[]> {
    const payload = await getJson<SessionHistoryResponse>(`/api/sessions/${activeSessionId}/messages`);
    if (mountedRef.current) {
      setMessages(payload.messages);
    }
    return payload.messages;
  }

  async function loadSessionAttachments(activeSessionId: string): Promise<SessionAttachment[]> {
    const payload = await getJson<SessionAttachmentListResponse>(`/api/sessions/${activeSessionId}/attachments`);
    if (mountedRef.current) {
      setAttachments(payload.attachments);
    }
    return payload.attachments;
  }

  async function loadSessionState(activeSessionId: string): Promise<void> {
    await Promise.all([loadSessionHistory(activeSessionId), loadSessionAttachments(activeSessionId)]);
  }

  async function createFreshSession(): Promise<string> {
    const payload = await postJson<SessionCreateResponse>("/api/sessions");
    if (!mountedRef.current) {
      return payload.session_id;
    }

    setSessionId(payload.session_id);
    storeSessionId(payload.session_id);
    setMessages([]);
    setAttachments([]);
    return payload.session_id;
  }

  async function restoreOrCreateSession(): Promise<void> {
    const storedSessionId = readStoredSessionId();
    if (!storedSessionId) {
      await createFreshSession();
      return;
    }

    if (!mountedRef.current) {
      return;
    }

    setSessionId(storedSessionId);
    storeSessionId(storedSessionId);
    try {
      await loadSessionState(storedSessionId);
    } catch {
      await createFreshSession();
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    void (async () => {
      setIsBootstrapping(true);
      setError(null);
      try {
        await restoreOrCreateSession();
      } catch (error) {
        if (mountedRef.current) {
          setError(error instanceof Error ? error.message : "Unknown error");
        }
      } finally {
        if (mountedRef.current) {
          setIsBootstrapping(false);
        }
      }
    })();

    return () => {
      mountedRef.current = false;
    };
  }, []);

  return {
    sessionId,
    messages,
    attachments,
    error,
    isBootstrapping,
    isSending: pendingMode !== null,
    isRunningMission: pendingMode === "mission",
    isUploadingAttachments,
    deletingAttachmentId,
    createSession: async () => {
      setIsBootstrapping(true);
      setError(null);
      try {
        await createFreshSession();
      } catch (error) {
        setError(error instanceof Error ? error.message : "Unknown error");
      } finally {
        if (mountedRef.current) {
          setIsBootstrapping(false);
        }
      }
    },
    sendMessage: async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || pendingMode !== null) {
        return;
      }

      setError(null);
      setPendingMode("chat");

      try {
        const activeSessionId = sessionId ?? (await createFreshSession());
        if (!mountedRef.current) {
          return;
        }

        const allowSensitiveTools = safetyConfirmationRequired
          ? requestSensitiveToolApproval("chat")
          : undefined;

        setMessages((current) => [...current, { role: "user", content: trimmed }]);

        await streamTurn("/api/chat/stream", {
          session_id: activeSessionId,
          message: trimmed,
          allow_sensitive_tools: allowSensitiveTools,
        } satisfies ChatTurnRequest, (content) => {
          if (!mountedRef.current) {
            return;
          }
          setMessages((current) => upsertAssistantSnapshot(current, content));
        });

        if (mountedRef.current) {
          await loadSessionHistory(activeSessionId);
        }
      } catch (error) {
        if (mountedRef.current) {
          setError(error instanceof Error ? error.message : "Unknown error");
        }
      } finally {
        if (mountedRef.current) {
          setPendingMode(null);
        }
      }
    },
    runMission: async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || pendingMode !== null) {
        return;
      }

      setError(null);
      setPendingMode("mission");

      try {
        const activeSessionId = sessionId ?? (await createFreshSession());
        if (!mountedRef.current) {
          return;
        }

        const allowSensitiveTools = safetyConfirmationRequired
          ? requestSensitiveToolApproval("mission")
          : undefined;

        const missionPrompt = `/mission ${trimmed}`;
        setMessages((current) => [...current, { role: "user", content: missionPrompt }]);

        await streamTurn("/api/missions/stream", {
          session_id: activeSessionId,
          message: trimmed,
          allow_sensitive_tools: allowSensitiveTools,
        } satisfies ChatTurnRequest, (content) => {
          if (!mountedRef.current) {
            return;
          }

          setMessages((current) => upsertAssistantSnapshot(current, content));
        });

        if (mountedRef.current) {
          await loadSessionHistory(activeSessionId);
        }
      } catch (error) {
        if (mountedRef.current) {
          setError(error instanceof Error ? error.message : "Unknown error");
        }
      } finally {
        if (mountedRef.current) {
          setPendingMode(null);
        }
      }
    },
    uploadAttachments: async (files: File[]) => {
      if (files.length === 0 || isUploadingAttachments || deletingAttachmentId !== null || pendingMode !== null) {
        return;
      }

      let activeSessionId: string | null = sessionId;
      setError(null);
      setIsUploadingAttachments(true);

      try {
        activeSessionId = activeSessionId ?? (await createFreshSession());
        if (!mountedRef.current || activeSessionId === null) {
          return;
        }

        for (const file of files) {
          await uploadAttachment<SessionAttachment>(`/api/sessions/${activeSessionId}/attachments`, file);
        }

        if (mountedRef.current) {
          await loadSessionAttachments(activeSessionId);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        if (mountedRef.current) {
          setError(message);
          if (activeSessionId !== null) {
            try {
              await loadSessionAttachments(activeSessionId);
            } catch {
              // Keep the original upload error when the follow-up refresh also fails.
            }
          }
        }
        throw error instanceof Error ? error : new Error(message);
      } finally {
        if (mountedRef.current) {
          setIsUploadingAttachments(false);
        }
      }
    },
    deleteAttachment: async (attachmentId: string) => {
      if (!sessionId || deletingAttachmentId !== null || isUploadingAttachments || pendingMode !== null) {
        return;
      }

      setError(null);
      setDeletingAttachmentId(attachmentId);

      try {
        await requestJson(`/api/sessions/${sessionId}/attachments/${attachmentId}`, {
          method: "DELETE",
        });

        if (mountedRef.current) {
          await loadSessionAttachments(sessionId);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        if (mountedRef.current) {
          setError(message);
        }
        throw error instanceof Error ? error : new Error(message);
      } finally {
        if (mountedRef.current) {
          setDeletingAttachmentId(null);
        }
      }
    },
  };
}