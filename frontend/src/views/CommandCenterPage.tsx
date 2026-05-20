import { CheckCircle2, Command, FolderSync, RefreshCw } from "lucide-react";

import { CommandCenterPanel } from "../components/CommandCenterPanel";
import { WorkspaceHeader } from "../components/WorkspaceHeader";
import type {
  CommandCenterOverview,
  MCPConfigurationApplyRequest,
  MCPConfigurationApplyResponse,
  MemoryBrainRepair,
  RuntimeVerification,
} from "../types/api";

interface CommandCenterPageProps {
  overview: CommandCenterOverview | null;
  verification: RuntimeVerification | null;
  memoryRepair: MemoryBrainRepair | null;
  error: string | null;
  isLoading: boolean;
  isRefreshingMcp: boolean;
  isApplyingMcp: boolean;
  isVerifying: boolean;
  isRepairingMemory: boolean;
  onRefresh: () => Promise<void>;
  onRefreshMcp: () => Promise<void>;
  onApplyMcp: (payload: MCPConfigurationApplyRequest) => Promise<MCPConfigurationApplyResponse>;
  onVerify: () => Promise<void>;
  onRepairMemory: () => Promise<MemoryBrainRepair>;
}

export function CommandCenterPage({
  overview,
  verification,
  memoryRepair,
  error,
  isLoading,
  isRefreshingMcp,
  isApplyingMcp,
  isVerifying,
  isRepairingMemory,
  onRefresh,
  onRefreshMcp,
  onApplyMcp,
  onVerify,
  onRepairMemory,
}: CommandCenterPageProps) {
  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="Command Center"
        title="Control Center"
        subtitle="Browser-native inspection for command coverage, MCP routing, tool inventory, and the verification flow that used to live in terminal-first operations."
        icon={Command}
        actions={
          <>
            <button type="button" onClick={() => void onRefresh()} className="rounded p-2 text-text-muted transition hover:bg-surface-container-low hover:text-primary">
              <RefreshCw className="h-5 w-5" />
            </button>
            <button type="button" onClick={() => void onVerify()} className="rounded p-2 text-text-muted transition hover:bg-surface-container-low hover:text-primary">
              <FolderSync className="h-5 w-5" />
            </button>
            <div className="rounded p-2 text-emerald-600">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </>
        }
      />

      <CommandCenterPanel
        overview={overview}
        verification={verification}
        memoryRepair={memoryRepair}
        error={error}
        isLoading={isLoading}
        isRefreshingMcp={isRefreshingMcp}
        isApplyingMcp={isApplyingMcp}
        isVerifying={isVerifying}
        isRepairingMemory={isRepairingMemory}
        onRefresh={onRefresh}
        onRefreshMcp={onRefreshMcp}
        onApplyMcp={onApplyMcp}
        onVerify={onVerify}
        onRepairMemory={onRepairMemory}
      />
    </div>
  );
}