import { ChatWorkspace } from "../components/ChatWorkspace";
import type { CommandCenterOverview, CommandReference, SessionAttachment, SessionMessage } from "../types/api";

interface ChatPageProps {
  sessionId: string | null;
  messages: SessionMessage[];
  attachments: SessionAttachment[];
  commandCenterOverview: CommandCenterOverview | null;
  error: string | null;
  isBootstrapping: boolean;
  isSending: boolean;
  isRunningMission: boolean;
  isUploadingAttachments: boolean;
  deletingAttachmentId: string | null;
  commands: CommandReference[];
  onNewSession: () => Promise<void>;
  onSendMessage: (message: string) => Promise<void>;
  onRunMission: (message: string) => Promise<void>;
  onUploadAttachments: (files: File[]) => Promise<void>;
  onDeleteAttachment: (attachmentId: string) => Promise<void>;
  onRefreshMcp: () => Promise<void>;
  onReloadTools: () => Promise<void>;
  onPrepareRuntime: () => Promise<void>;
  onVerifyRuntime: () => Promise<void>;
}

export function ChatPage({
  sessionId,
  messages,
  attachments,
  commandCenterOverview,
  error,
  isBootstrapping,
  isSending,
  isRunningMission,
  isUploadingAttachments,
  deletingAttachmentId,
  commands,
  onNewSession,
  onSendMessage,
  onRunMission,
  onUploadAttachments,
  onDeleteAttachment,
  onRefreshMcp,
  onReloadTools,
  onPrepareRuntime,
  onVerifyRuntime,
}: ChatPageProps) {
  return (
    <ChatWorkspace
      sessionId={sessionId}
      messages={messages}
      attachments={attachments}
      commandCenterOverview={commandCenterOverview}
      error={error}
      isBootstrapping={isBootstrapping}
      isSending={isSending}
      isRunningMission={isRunningMission}
      isUploadingAttachments={isUploadingAttachments}
      deletingAttachmentId={deletingAttachmentId}
      commands={commands}
      onNewSession={onNewSession}
      onSendMessage={onSendMessage}
      onRunMission={onRunMission}
      onUploadAttachments={onUploadAttachments}
      onDeleteAttachment={onDeleteAttachment}
      onRefreshMcp={onRefreshMcp}
      onReloadTools={onReloadTools}
      onPrepareRuntime={onPrepareRuntime}
      onVerifyRuntime={onVerifyRuntime}
    />
  );
}