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

  listWorkspaces: () => request<Workspace[]>('/api/workspaces'),

  createWorkspace: (name: string, description?: string) =>
    request<Workspace>('/api/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),

  getWorkspace: (workspaceId: string) => request<Workspace>(`/api/workspaces/${workspaceId}`),

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

  sendMessage: (workspaceId: string, conversationId: string, content: string) =>
    request<{ user_message: Message; assistant_message: Message }>(
      `/api/workspaces/${workspaceId}/conversations/${conversationId}/messages`,
      { method: 'POST', body: JSON.stringify({ content }) }
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
}
