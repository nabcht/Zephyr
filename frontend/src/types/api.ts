export interface StartupAction {
  level: string;
  badge: string;
  label: string;
  summary: string;
  command: string | null;
  supports_prepare: boolean;
}

export interface StartupGuidance {
  level: string;
  badge: string;
  title: string;
  actions: StartupAction[];
}

export interface PrivacyStatus {
  level: string;
  badge: string;
  title: string;
  summary: string;
  inference_backend: string;
  remote_capabilities: string[];
}

export interface TrustSignal {
  label: string;
  level: string;
  badge: string;
  summary: string;
}

export interface RuntimeTrustStatus {
  level: string;
  badge: string;
  title: string;
  signals: TrustSignal[];
}

export interface ToolCounts {
  total: number;
  skill_tools: number;
  builtins: number;
  mcp_tools: number;
  manual_tools: number;
}

export interface InferenceMetrics {
  last_warmup_ms: number | null;
  last_warmup_outcome: string;
  last_completion_ms: number | null;
  last_completion_outcome: string;
}

export interface SystemStatus {
  name: string;
  version: string;
  provider: string;
  model: string;
  interfaces: string[];
  runtime_initialized: boolean;
  inference_status: string;
  inference_metrics: InferenceMetrics;
  search_status: string;
  external_integrations_enabled: boolean;
  safety_confirmation_required: boolean;
  design_system_path: string;
  prepare_actions: string[];
  tool_counts: ToolCounts;
  privacy_status: PrivacyStatus;
  trust_status: RuntimeTrustStatus;
  startup_guidance: StartupGuidance;
}

export interface SessionCreateResponse {
  session_id: string;
}

export interface SessionMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface SessionHistoryResponse {
  session_id: string;
  messages: SessionMessage[];
}

export interface ChatTurnRequest {
  session_id: string;
  message: string;
  allow_sensitive_tools?: boolean;
}

export interface ChatTurnResponse {
  session_id: string;
  response: string;
}

export interface ChatStreamEvent {
  content: string;
  done: boolean;
}

export interface RuntimePreparationResponse {
  success: boolean;
  lines: string[];
  status: SystemStatus;
}

export interface RuntimeActionStreamEvent {
  action: "reload" | "prepare";
  stage: string;
  message: string;
  lines: string[];
  done: boolean;
  success: boolean | null;
  status: SystemStatus | null;
}

export interface CommandReference {
  command: string;
  description: string;
  web_available: boolean;
  web_label: string | null;
}

export interface ToolCatalogEntry {
  name: string;
  description: string;
  source: string;
  source_label: string;
  tags: string[];
}

export interface MCPServerStatus {
  name: string;
  tool_prefix: string;
  command: string;
  args: string[];
  connected: boolean;
  discovered_tools: string[];
  state: "ready" | "connected" | "error";
  last_error: string | null;
  last_discovered_at: string | null;
  last_successful_connection_at: string | null;
  last_error_kind: "configuration" | "dependency" | "connection" | "execution" | "remote" | null;
  last_error_tool_name: string | null;
  degraded_reason: string | null;
}

export interface MCPToolExecution {
  tool_name: string;
  executed_at: string;
  display_text: string;
  structured_content: unknown | null;
  structured_content_type: string | null;
  structured_content_preview: string | null;
  is_error: boolean;
  error_type: string | null;
}

export interface MCPOverview {
  enabled: boolean;
  external_integrations_enabled: boolean;
  configured: boolean;
  message: string;
  servers: MCPServerStatus[];
  recent_executions: MCPToolExecution[];
}

export interface DurableMemory {
  facts: string[];
}

export interface CommandCenterOverview {
  runtime_initialized: boolean;
  commands: CommandReference[];
  tools: ToolCatalogEntry[];
  mcp: MCPOverview;
  memory: DurableMemory;
}

export interface RuntimeVerification {
  valid_skills: string[];
  repaired_skills: string[];
  broken_skills: string[];
  sandbox_readiness: string[];
  truth_synthesis: string[];
  startup_guidance: string[];
  eval_summary: string | null;
}