const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('access_token')
  const isFormData = options.body instanceof FormData
  const headers: HeadersInit = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(response.status, body.detail ?? 'Request failed')
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
}

export interface Workspace {
  id: string
  owner_id: string
  name: string
  description: string | null
}

export interface Assistant {
  id: string
  workspace_id: string
  name: string
  role: string | null
  system_prompt: string | null
  personality: string | null
  response_style: string
  model_provider: string
  model_name: string | null
  temperature: number
  max_tokens: number
}

export type AssistantUpdate = Partial<
  Omit<Assistant, 'id' | 'workspace_id'>
>

export interface Conversation {
  id: string
  workspace_id: string
  assistant_id: string | null
  title: string | null
  created_at: string
  updated_at: string
}

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

export interface Citation {
  document_id: string
  filename: string
  chunk_index: number
  snippet: string
  score: number
}

export interface Message {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  citations: Citation[] | null
  pinned: boolean
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface WorkspaceDocument {
  id: string
  workspace_id: string
  filename: string
  mime_type: string | null
  size_bytes: number | null
  status: DocumentStatus
  created_at: string
}

export interface MemoryEntry {
  id: string
  workspace_id: string
  key: string
  value: string
  memory_type: 'short_term' | 'long_term' | 'summary'
  pinned: boolean
  created_at: string
  updated_at: string
}

export const PROMPT_CATEGORIES = ['writing', 'programming', 'research', 'business', 'education', 'custom'] as const
export type PromptCategory = (typeof PROMPT_CATEGORIES)[number]

export interface PromptTemplate {
  id: string
  workspace_id: string
  name: string
  content: string
  category: string
  created_at: string
  updated_at: string
}

export interface Skill {
  id: string
  workspace_id: string
  name: string
  description: string | null
  category: string
  enabled: boolean
}

export interface SkillRunResult {
  output: string
  user_message: Message | null
  assistant_message: Message | null
}

export interface DashboardData {
  counts: {
    conversations: number
    messages: number
    documents: number
    memory_items: number
    prompt_templates: number
    skills: number
  }
  usage: {
    total_input_tokens: number
    total_output_tokens: number
    estimated_cost_usd: number
  }
  recent_activity: { type: string; title: string; timestamp: string }[]
}

export type ModelCatalog = Record<string, string[]>

// --- Week 6: Observability / Guardrails / Evaluation / Versioning / Quality ---

export type TraceType = 'chat' | 'skill' | 'embedding' | 'memory_extraction' | 'tool_call' | 'evaluation'
export type TraceStatus = 'success' | 'error' | 'timeout' | 'retried' | 'degraded'

export interface Trace {
  id: string
  trace_id: string
  trace_type: TraceType
  provider: string | null
  model: string | null
  conversation_id: string | null
  message_id: string | null
  input_tokens: number
  output_tokens: number
  cost_usd: number
  input_cost_usd: number | null
  output_cost_usd: number | null
  latency_ms: number
  status: TraceStatus
  error_message: string | null
  retry_count: number
  evaluation_run_id: string | null
  eval_case_id: string | null
  meta: Record<string, unknown> | null
  created_at: string
}

export interface TraceListResult {
  items: Trace[]
  total: number
}

export type GuardrailDirection = 'input' | 'output'
export type GuardrailAction = 'blocked' | 'flagged' | 'sanitized' | 'approved'

export interface GuardrailEvent {
  id: string
  conversation_id: string | null
  message_id: string | null
  direction: GuardrailDirection
  guardrail_type: string
  triggered: boolean
  action: GuardrailAction
  detail: Record<string, unknown> | null
  created_at: string
}

export interface GuardrailEventListResult {
  items: GuardrailEvent[]
  total: number
}

export type PendingActionStatus = 'pending' | 'approved' | 'rejected'

export interface PendingAction {
  id: string
  conversation_id: string | null
  tool_name: string
  tool_args: Record<string, unknown> | null
  risk_level: string
  status: PendingActionStatus
  result: Record<string, unknown> | null
  created_at: string
}

export interface AgentStep {
  tool_name: string
  arguments: Record<string, unknown>
  result: Record<string, unknown> | null
  error: string | null
}

export interface SendMessageResult {
  user_message: Message
  assistant_message: Message
  agent_steps: AgentStep[] | null
  pending_action_id: string | null
  hit_loop_limit: boolean
}

export interface EvaluationResultRow {
  id: string
  case_id: string
  category: string
  actual_output: string | null
  deterministic_result: Record<string, unknown> | null
  judge_score: number | null
  judge_reasoning: string | null
  rag_metrics: Record<string, unknown> | null
  agent_metrics: Record<string, unknown> | null
  latency_ms: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
  passed: boolean
  failure_category: string | null
}

export interface EvaluationRun {
  id: string
  name: string
  dataset_version: string
  prompt_version_id: string | null
  provider: string
  model: string
  status: 'running' | 'completed' | 'failed'
  summary: Record<string, any> | null
  created_at: string
}

export interface EvaluationRunDetail extends EvaluationRun {
  results: EvaluationResultRow[]
}

export interface EvaluationRunListResult {
  items: EvaluationRun[]
  total: number
}

export interface ComparisonResult {
  run_a_id: string
  run_b_id: string
  improved: number
  regressed: number
  unchanged: number
  cases: {
    case_id: string
    category: string
    status: 'improved' | 'regressed' | 'unchanged'
    run_a_passed: boolean
    run_b_passed: boolean
    run_a_judge_score: number | null
    run_b_judge_score: number | null
  }[]
}

export interface PromptVersion {
  id: string
  workspace_id: string
  assistant_id: string | null
  name: string
  version_label: string
  system_prompt: string
  notes: string | null
  is_active: boolean
  created_at: string
}

export interface QualityFilters {
  [key: string]: string | undefined
  since?: string
  until?: string
  model?: string
}

export interface QualityOverview {
  latest_run_id: string | null
  task_success_rate: number | null
  avg_judge_score: number | null
  n_cases: number | null
  request_count: number
  successful_requests: number
  failed_requests: number
  failure_rate: number | null
  guardrail_trigger_count: number
  cost_usd: number
  cost_per_successful_task_usd: number | null
  latency_ms: { mean: number | null; median: number | null; p50: number | null; p95: number | null; p99: number | null }
  token_usage: { total: number; input: number; output: number }
  by_model: Record<string, { n_requests: number; total_cost_usd: number; total_tokens: number }>
  by_prompt_version: Record<string, { n_requests: number; n_successful: number; avg_latency_ms: number; success_rate: number }>
}

export interface QualityPerformance {
  n_requests: number
  successful_requests: number
  failed_requests: number
  latency_ms: { mean: number | null; median: number | null; p50: number | null; p95: number | null; p99: number | null }
  cost: {
    total_usd: number
    input_usd: number
    output_usd: number
    per_request_usd: number
    per_successful_task_usd: number | null
  }
  tokens: { total: number; input: number; output: number }
  by_model: Record<string, { n_requests: number; total_cost_usd: number; total_tokens: number }>
  by_trace_type: Record<string, { n_requests: number; avg_latency_ms: number; total_cost_usd: number }>
  by_prompt_version: Record<string, { n_requests: number; n_successful: number; avg_latency_ms: number; success_rate: number }>
  reliability: { retry_rate: number | null; timeout_rate: number | null; error_rate: number | null; degraded_rate: number | null }
  bottlenecks: { stage: string; avg_latency_ms: number; n_requests: number }[]
  latency_by_stage: Record<string, { mean: number | null; median: number | null; p50: number | null; p95: number | null; p99: number | null }>
  bottleneck_stage: string | null
}

export interface QualityReliability {
  successful_requests: number
  failed_requests: number
  retry_rate: number | null
  timeout_rate: number | null
  error_rate: number | null
  degraded_rate: number | null
  guardrail_events_by_action: Record<string, number>
  guardrail_events_by_type: Record<string, number>
  blocked_count: number
  flagged_count: number
  sanitized_count: number
}

export const api = {
  register: (email: string, password: string, fullName?: string) =>
    request<User>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName }),
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>('/api/auth/me'),

  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),

  listWorkspaces: () => request<Workspace[]>('/api/workspaces'),

  createWorkspace: (name: string, description?: string) =>
    request<Workspace>('/api/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),

  getWorkspace: (workspaceId: string) => request<Workspace>(`/api/workspaces/${workspaceId}`),

  renameWorkspace: (workspaceId: string, name: string) =>
    request<Workspace>(`/api/workspaces/${workspaceId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),

  deleteWorkspace: (workspaceId: string) =>
    request<void>(`/api/workspaces/${workspaceId}`, { method: 'DELETE' }),

  getAssistant: (workspaceId: string) => request<Assistant>(`/api/workspaces/${workspaceId}/assistant`),

  updateAssistant: (workspaceId: string, payload: AssistantUpdate) =>
    request<Assistant>(`/api/workspaces/${workspaceId}/assistant`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  listConversations: (workspaceId: string, query?: string) =>
    request<Conversation[]>(
      `/api/workspaces/${workspaceId}/conversations${query ? `?q=${encodeURIComponent(query)}` : ''}`
    ),

  createConversation: (workspaceId: string, title?: string) =>
    request<Conversation>(`/api/workspaces/${workspaceId}/conversations`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),

  getConversation: (workspaceId: string, conversationId: string) =>
    request<ConversationDetail>(`/api/workspaces/${workspaceId}/conversations/${conversationId}`),

  renameConversation: (workspaceId: string, conversationId: string, title: string) =>
    request<Conversation>(`/api/workspaces/${workspaceId}/conversations/${conversationId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (workspaceId: string, conversationId: string) =>
    request<void>(`/api/workspaces/${workspaceId}/conversations/${conversationId}`, {
      method: 'DELETE',
    }),

  sendMessage: (workspaceId: string, conversationId: string, content: string, mode: 'chat' | 'agent' = 'chat') =>
    request<SendMessageResult>(
      `/api/workspaces/${workspaceId}/conversations/${conversationId}/messages`,
      { method: 'POST', body: JSON.stringify({ content, mode }) }
    ),

  listDocuments: (workspaceId: string) => request<WorkspaceDocument[]>(`/api/workspaces/${workspaceId}/documents`),

  uploadDocument: (workspaceId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<WorkspaceDocument>(`/api/workspaces/${workspaceId}/documents`, {
      method: 'POST',
      body: formData,
    })
  },

  deleteDocument: (workspaceId: string, documentId: string) =>
    request<void>(`/api/workspaces/${workspaceId}/documents/${documentId}`, { method: 'DELETE' }),

  listMemory: (workspaceId: string) => request<MemoryEntry[]>(`/api/workspaces/${workspaceId}/memory`),

  createMemory: (workspaceId: string, key: string, value: string, pinned = true) =>
    request<MemoryEntry>(`/api/workspaces/${workspaceId}/memory`, {
      method: 'POST',
      body: JSON.stringify({ key, value, pinned }),
    }),

  updateMemory: (workspaceId: string, memoryId: string, payload: { value?: string; pinned?: boolean }) =>
    request<MemoryEntry>(`/api/workspaces/${workspaceId}/memory/${memoryId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteMemory: (workspaceId: string, memoryId: string) =>
    request<void>(`/api/workspaces/${workspaceId}/memory/${memoryId}`, { method: 'DELETE' }),

  setMessagePinned: (workspaceId: string, conversationId: string, messageId: string, pinned: boolean) =>
    request<Message>(`/api/workspaces/${workspaceId}/conversations/${conversationId}/messages/${messageId}`, {
      method: 'PATCH',
      body: JSON.stringify({ pinned }),
    }),

  listPinnedMessages: (workspaceId: string, conversationId: string) =>
    request<Message[]>(`/api/workspaces/${workspaceId}/conversations/${conversationId}/pinned-messages`),

  listPrompts: (workspaceId: string, category?: string) =>
    request<PromptTemplate[]>(
      `/api/workspaces/${workspaceId}/prompts${category ? `?category=${encodeURIComponent(category)}` : ''}`
    ),

  createPrompt: (workspaceId: string, name: string, content: string, category: string) =>
    request<PromptTemplate>(`/api/workspaces/${workspaceId}/prompts`, {
      method: 'POST',
      body: JSON.stringify({ name, content, category }),
    }),

  updatePrompt: (workspaceId: string, promptId: string, payload: Partial<Pick<PromptTemplate, 'name' | 'content' | 'category'>>) =>
    request<PromptTemplate>(`/api/workspaces/${workspaceId}/prompts/${promptId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deletePrompt: (workspaceId: string, promptId: string) =>
    request<void>(`/api/workspaces/${workspaceId}/prompts/${promptId}`, { method: 'DELETE' }),

  listSkills: (workspaceId: string) => request<Skill[]>(`/api/workspaces/${workspaceId}/skills`),

  runSkill: (workspaceId: string, skillId: string, input: string, conversationId?: string) =>
    request<SkillRunResult>(`/api/workspaces/${workspaceId}/skills/${skillId}/run`, {
      method: 'POST',
      body: JSON.stringify({ input, conversation_id: conversationId }),
    }),

  getDashboard: (workspaceId: string) => request<DashboardData>(`/api/workspaces/${workspaceId}/dashboard`),

  listModels: () => request<ModelCatalog>('/api/models'),

  // --- Observability ---
  listTraces: (workspaceId: string, params?: { trace_type?: string; status?: string; limit?: number }) =>
    request<TraceListResult>(`/api/workspaces/${workspaceId}/traces${toQuery(params)}`),

  getTrace: (workspaceId: string, traceId: string) =>
    request<Trace>(`/api/workspaces/${workspaceId}/traces/${traceId}`),

  // --- Guardrails ---
  listGuardrailEvents: (workspaceId: string, params?: { guardrail_type?: string; action?: string; limit?: number }) =>
    request<GuardrailEventListResult>(`/api/workspaces/${workspaceId}/guardrail-events${toQuery(params)}`),

  listPendingActions: (workspaceId: string, status?: PendingActionStatus) =>
    request<PendingAction[]>(`/api/workspaces/${workspaceId}/pending-actions${toQuery({ status })}`),

  decidePendingAction: (workspaceId: string, actionId: string, approve: boolean) =>
    request<PendingAction>(`/api/workspaces/${workspaceId}/pending-actions/${actionId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ approve }),
    }),

  // --- Evaluations ---
  runEvaluation: (
    workspaceId: string,
    payload: { name?: string; provider?: string; model?: string; prompt_version_id?: string; categories?: string[]; limit?: number; run_judge?: boolean }
  ) =>
    request<EvaluationRun>(`/api/workspaces/${workspaceId}/evaluations/run`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listEvaluationRuns: (workspaceId: string) =>
    request<EvaluationRunListResult>(`/api/workspaces/${workspaceId}/evaluations`),

  getEvaluationRun: (workspaceId: string, runId: string) =>
    request<EvaluationRunDetail>(`/api/workspaces/${workspaceId}/evaluations/${runId}`),

  compareEvaluationRuns: (workspaceId: string, runA: string, runB: string) =>
    request<ComparisonResult>(`/api/workspaces/${workspaceId}/evaluations/compare?run_a=${runA}&run_b=${runB}`),

  getHumanComparison: (workspaceId: string, runId: string) =>
    request<Record<string, unknown>>(`/api/workspaces/${workspaceId}/evaluations/${runId}/human-comparison`),

  // --- Prompt versions ---
  listPromptVersions: (workspaceId: string) =>
    request<PromptVersion[]>(`/api/workspaces/${workspaceId}/prompt-versions`),

  createPromptVersion: (
    workspaceId: string,
    payload: { name: string; version_label: string; system_prompt: string; notes?: string }
  ) =>
    request<PromptVersion>(`/api/workspaces/${workspaceId}/prompt-versions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updatePromptVersion: (workspaceId: string, versionId: string, payload: { is_active?: boolean; notes?: string }) =>
    request<PromptVersion>(`/api/workspaces/${workspaceId}/prompt-versions/${versionId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // --- Quality dashboard ---
  getQualityOverview: (workspaceId: string, filters?: QualityFilters) =>
    request<QualityOverview>(`/api/workspaces/${workspaceId}/quality/overview${toQuery(filters)}`),

  getQualityRag: (workspaceId: string) => request<Record<string, unknown>>(`/api/workspaces/${workspaceId}/quality/rag`),

  getQualityAgent: (workspaceId: string) =>
    request<Record<string, unknown>>(`/api/workspaces/${workspaceId}/quality/agent`),

  getQualityPerformance: (workspaceId: string, filters?: QualityFilters) =>
    request<QualityPerformance>(`/api/workspaces/${workspaceId}/quality/performance${toQuery(filters)}`),

  getQualityReliability: (workspaceId: string, filters?: QualityFilters) =>
    request<QualityReliability>(`/api/workspaces/${workspaceId}/quality/reliability${toQuery(filters)}`),
}

function toQuery(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return ''
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  if (entries.length === 0) return ''
  const search = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))
  return `?${search.toString()}`
}
