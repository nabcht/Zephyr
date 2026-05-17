import { useEffect, useState } from "react";

import { AppShell, type AppView } from "./components/AppShell";
import { useChatSession } from "./hooks/useChatSession";
import { useCommandCenter } from "./hooks/useCommandCenter";
import { useSystemStatus } from "./hooks/useSystemStatus";
import { ActivityPage } from "./views/ActivityPage";
import { ChatPage } from "./views/ChatPage";
import { CommandCenterPage } from "./views/CommandCenterPage";
import { PosturePage } from "./views/PosturePage";

function resolveViewFromHash(hash: string): AppView {
  switch (hash.replace(/^#/, "")) {
    case "command-center":
      return "command-center";
    case "posture":
      return "posture";
    case "activity":
      return "activity";
    default:
      return "chat";
  }
}

function hashForView(view: AppView): string {
  switch (view) {
    case "command-center":
      return "#command-center";
    case "posture":
      return "#posture";
    case "activity":
      return "#activity";
    default:
      return "#chat";
  }
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export default function App() {
  const [activeView, setActiveView] = useState<AppView>(() => {
    if (typeof window === "undefined") {
      return "chat";
    }

    return resolveViewFromHash(window.location.hash);
  });
  const {
    status,
    error: statusError,
    isLoading,
    isReloading,
    isPreparing,
    prepareResult,
    runtimeActivity,
    refresh,
    reloadRuntime,
    prepareRuntime,
  } = useSystemStatus();
  const {
    overview,
    verification,
    error: commandCenterError,
    isLoading: isCommandCenterLoading,
    isRefreshingMcp,
    isVerifying,
    refresh: refreshCommandCenter,
    refreshMcpDiscovery,
    verifyRuntime,
  } = useCommandCenter();
  const {
    sessionId,
    messages,
    error: chatError,
    isBootstrapping,
    isSending,
    isRunningMission,
    createSession,
    sendMessage,
    runMission,
  } = useChatSession(status?.safety_confirmation_required ?? false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const syncViewFromHash = () => {
      setActiveView(resolveViewFromHash(window.location.hash));
    };

    if (!window.location.hash) {
      window.history.replaceState(null, "", hashForView("chat"));
    }

    syncViewFromHash();
    window.addEventListener("hashchange", syncViewFromHash);
    return () => window.removeEventListener("hashchange", syncViewFromHash);
  }, []);

  async function handleRefreshSnapshot(): Promise<void> {
    await Promise.all([refresh(), refreshCommandCenter()]);
  }

  async function handleReloadTools(): Promise<void> {
    await reloadRuntime();
    await refreshCommandCenter();
  }

  async function handlePrepareRuntime(): Promise<void> {
    await prepareRuntime();
    await refreshCommandCenter();
  }

  async function handleVerifyRuntimeAndReveal(): Promise<void> {
    handleViewChange("command-center");
    await verifyRuntime();
  }

  function handleViewChange(view: AppView): void {
    setActiveView(view);

    if (typeof window === "undefined") {
      return;
    }

    const nextHash = hashForView(view);
    if (window.location.hash !== nextHash) {
      window.history.pushState(null, "", nextHash);
    }
  }

  const isRuntimeActionActive = isReloading || isPreparing;
  const privacyStatus = status?.privacy_status ?? {
    level: "yellow",
    badge: "...",
    title: "Loading privacy posture",
    summary: "Waiting for backend runtime status.",
    inference_backend: "Unknown",
    remote_capabilities: [],
  };
  const trustStatus = status?.trust_status ?? {
    level: "yellow",
    badge: "...",
    title: "Loading runtime trust",
    signals: [],
  };
  const startupGuidance = status?.startup_guidance ?? {
    level: "yellow",
    badge: "...",
    title: isLoading ? "Loading startup guidance" : "Startup guidance unavailable",
    actions: [],
  };

  let pageContent: JSX.Element;
  switch (activeView) {
    case "command-center":
      pageContent = (
        <CommandCenterPage
          overview={overview}
          verification={verification}
          error={commandCenterError}
          isLoading={isCommandCenterLoading}
          isRefreshingMcp={isRefreshingMcp}
          isVerifying={isVerifying}
          onRefresh={refreshCommandCenter}
          onRefreshMcp={refreshMcpDiscovery}
          onVerify={verifyRuntime}
        />
      );
      break;
    case "posture":
      pageContent = (
        <PosturePage
          privacyStatus={privacyStatus}
          trustStatus={trustStatus}
          memoryFacts={overview?.memory.facts ?? []}
        />
      );
      break;
    case "activity":
      pageContent = (
        <ActivityPage
          status={status}
          isStatusLoading={isLoading}
          activity={runtimeActivity}
          prepareResult={prepareResult}
          verification={verification}
          isReloading={isReloading}
          isPreparing={isPreparing}
          safetyConfirmationRequired={status?.safety_confirmation_required ?? null}
          startupGuidance={startupGuidance}
          onPrepareRuntime={handlePrepareRuntime}
        />
      );
      break;
    case "chat":
    default:
      pageContent = (
        <ChatPage
          sessionId={sessionId}
          messages={messages}
          error={chatError}
          isBootstrapping={isBootstrapping}
          isSending={isSending}
          isRunningMission={isRunningMission}
          onNewSession={createSession}
          onSendMessage={sendMessage}
          onRunMission={runMission}
        />
      );
      break;
  }

  return (
    <AppShell
      activeView={activeView}
      onViewChange={handleViewChange}
      status={status}
      sessionId={sessionId}
      isLoading={isLoading}
      onRefreshSnapshot={handleRefreshSnapshot}
      onReloadTools={handleReloadTools}
      onVerifyRuntime={handleVerifyRuntimeAndReveal}
      isReloading={isReloading}
      isRuntimeBusy={isRuntimeActionActive}
      isVerifying={isVerifying}
    >
      {statusError ? (
        <section className="mb-6 rounded-3xl border border-red-200 bg-red-50 p-5 text-red-900">
          <p className="text-xs uppercase tracking-[0.24em] text-red-700/70">Backend status</p>
          <h2 className="mt-2 text-xl font-semibold">Unable to load system status</h2>
          <p className="mt-3 text-sm leading-6">{statusError}</p>
        </section>
      ) : null}

      {pageContent}
    </AppShell>
  );
}