import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { AppShell, type AppView } from "./components/AppShell";
import { useChatSession } from "./hooks/useChatSession";
import { useCommandCenter } from "./hooks/useCommandCenter";
import { useSystemStatus } from "./hooks/useSystemStatus";
import { ActivityPage } from "./views/ActivityPage";
import { ChatPage } from "./views/ChatPage";
import { CommandCenterPage } from "./views/CommandCenterPage";
import {
  ApiDocsPage,
  DocsPage,
  GlossaryPage,
  PrivacyPage,
  ProfilePage,
  SettingsPage,
  SupportPage,
  TermsPage,
} from "./views/NavigationPages";
import { PosturePage } from "./views/PosturePage";

function normalizePathname(pathname: string): string {
  if (!pathname || pathname === "/") {
    return "/";
  }

  return pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
}

function resolveViewFromPath(pathname: string): AppView | null {
  switch (normalizePathname(pathname)) {
    case "/chat":
      return "chat";
    case "/docs":
      return "docs";
    case "/glossary":
      return "glossary";
    case "/support":
      return "support";
    case "/command-center":
      return "command-center";
    case "/settings":
      return "settings";
    case "/profile":
      return "profile";
    case "/posture":
      return "posture";
    case "/terms":
      return "terms";
    case "/privacy":
      return "privacy";
    case "/api-docs":
      return "api-docs";
    case "/activity":
      return "activity";
    default:
      return null;
  }
}

function pathForView(view: AppView): string {
  switch (view) {
    case "chat":
      return "/chat";
    case "docs":
      return "/docs";
    case "glossary":
      return "/glossary";
    case "support":
      return "/support";
    case "command-center":
      return "/command-center";
    case "settings":
      return "/settings";
    case "profile":
      return "/profile";
    case "posture":
      return "/posture";
    case "terms":
      return "/terms";
    case "privacy":
      return "/privacy";
    case "api-docs":
      return "/api-docs";
    case "activity":
      return "/activity";
  }
}

/**
 * Design reference: frontend/design.md -> Overview, Colors.
 */
export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
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
    isApplyingMcp,
    isVerifying,
    refresh: refreshCommandCenter,
    refreshMcpDiscovery,
    applyMcpConfiguration,
    verifyRuntime,
  } = useCommandCenter();
  const {
    sessionId,
    messages,
    attachments,
    error: chatError,
    isBootstrapping,
    isSending,
    isRunningMission,
    isUploadingAttachments,
    deletingAttachmentId,
    createSession,
    sendMessage,
    runMission,
    uploadAttachments,
    deleteAttachment,
  } = useChatSession(status?.safety_confirmation_required ?? false);

  const resolvedView = resolveViewFromPath(location.pathname);
  const activeView = resolvedView ?? "chat";

  useEffect(() => {
    const normalized = normalizePathname(location.pathname);

    if (normalized === "/") {
      navigate(pathForView("chat"), { replace: true });
      return;
    }

    if (resolvedView === null) {
      navigate(pathForView("chat"), { replace: true });
    }
  }, [location.pathname, navigate, resolvedView]);

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
    const nextPath = pathForView(view);
    if (normalizePathname(location.pathname) !== nextPath) {
      navigate(nextPath);
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
    case "docs":
      pageContent = <DocsPage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
      break;
    case "glossary":
      pageContent = <GlossaryPage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
      break;
    case "support":
      pageContent = <SupportPage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
      break;
    case "command-center":
      pageContent = (
        <CommandCenterPage
          overview={overview}
          verification={verification}
          error={commandCenterError}
          isLoading={isCommandCenterLoading}
          isRefreshingMcp={isRefreshingMcp}
          isApplyingMcp={isApplyingMcp}
          isVerifying={isVerifying}
          onRefresh={refreshCommandCenter}
          onRefreshMcp={refreshMcpDiscovery}
          onApplyMcp={applyMcpConfiguration}
          onVerify={verifyRuntime}
        />
      );
      break;
    case "settings":
      pageContent = <SettingsPage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
      break;
    case "profile":
      pageContent = <ProfilePage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
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
    case "terms":
      pageContent = <TermsPage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
      break;
    case "privacy":
      pageContent = <PrivacyPage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
      break;
    case "api-docs":
      pageContent = <ApiDocsPage status={status} sessionId={sessionId} onNavigate={handleViewChange} />;
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
          attachments={attachments}
          commandCenterOverview={overview}
          error={chatError}
          isBootstrapping={isBootstrapping}
          isSending={isSending}
          isRunningMission={isRunningMission}
          isUploadingAttachments={isUploadingAttachments}
          deletingAttachmentId={deletingAttachmentId}
          commands={overview?.commands ?? []}
          onNewSession={createSession}
          onSendMessage={sendMessage}
          onRunMission={runMission}
          onUploadAttachments={uploadAttachments}
          onDeleteAttachment={deleteAttachment}
          onRefreshMcp={refreshMcpDiscovery}
          onReloadTools={handleReloadTools}
          onPrepareRuntime={handlePrepareRuntime}
          onVerifyRuntime={verifyRuntime}
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