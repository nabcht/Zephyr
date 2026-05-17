import { ChatWorkspace } from "../components/ChatWorkspace";
import type { SessionMessage } from "../types/api";

interface ChatPageProps {
  sessionId: string | null;
  messages: SessionMessage[];
  error: string | null;
  isBootstrapping: boolean;
  isSending: boolean;
  isRunningMission: boolean;
  onNewSession: () => Promise<void>;
  onSendMessage: (message: string) => Promise<void>;
  onRunMission: (message: string) => Promise<void>;
}

export function ChatPage({
  sessionId,
  messages,
  error,
  isBootstrapping,
  isSending,
  isRunningMission,
  onNewSession,
  onSendMessage,
  onRunMission,
}: ChatPageProps) {
  return (
    <ChatWorkspace
      sessionId={sessionId}
      messages={messages}
      error={error}
      isBootstrapping={isBootstrapping}
      isSending={isSending}
      isRunningMission={isRunningMission}
      onNewSession={onNewSession}
      onSendMessage={onSendMessage}
      onRunMission={onRunMission}
    />
  );
}