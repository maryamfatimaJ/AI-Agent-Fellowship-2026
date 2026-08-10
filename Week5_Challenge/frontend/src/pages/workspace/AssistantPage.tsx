import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { api, type Assistant, type ModelCatalog } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

const RESPONSE_STYLES = ['concise', 'balanced', 'detailed', 'friendly']

export function AssistantPage() {
  const { workspaceId = '' } = useParams()
  const [assistant, setAssistant] = useState<Assistant | null>(null)
  const [models, setModels] = useState<ModelCatalog>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  useEffect(() => {
    Promise.all([api.getAssistant(workspaceId), api.listModels()])
      .then(([assistantData, modelData]) => {
        setAssistant(assistantData)
        setModels(modelData)
      })
      .finally(() => setIsLoading(false))
  }, [workspaceId])

  function update<K extends keyof Assistant>(key: K, value: Assistant[K]) {
    setAssistant((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  async function handleSave() {
    if (!assistant) return
    setIsSaving(true)
    try {
      const updated = await api.updateAssistant(workspaceId, {
        name: assistant.name,
        role: assistant.role,
        system_prompt: assistant.system_prompt,
        personality: assistant.personality,
        response_style: assistant.response_style,
        model_provider: assistant.model_provider,
        model_name: assistant.model_name,
        temperature: assistant.temperature,
        max_tokens: assistant.max_tokens,
      })
      setAssistant(updated)
      setSavedAt(Date.now())
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) return <EmptyState title="Loading assistant settings…" />
  if (!assistant) return <EmptyState title="Could not load assistant settings." />

  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto px-6 py-10">
      <div className="mb-8 space-y-1">
        <h1 className="text-lg font-medium text-ink">Assistant</h1>
        <p className="text-sm text-ink-muted">Configure how this workspace's assistant behaves.</p>
      </div>

      <div className="space-y-5">
        <Field label="Name">
          <input
            value={assistant.name}
            onChange={(e) => update('name', e.target.value)}
            className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
          />
        </Field>

        <Field label="Role">
          <input
            value={assistant.role ?? ''}
            onChange={(e) => update('role', e.target.value)}
            placeholder="e.g. Research assistant, coding partner, editor"
            className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
        </Field>

        <Field label="System prompt">
          <textarea
            value={assistant.system_prompt ?? ''}
            onChange={(e) => update('system_prompt', e.target.value)}
            rows={4}
            placeholder="Instructions the assistant should always follow."
            className="w-full resize-none rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
        </Field>

        <Field label="Personality">
          <input
            value={assistant.personality ?? ''}
            onChange={(e) => update('personality', e.target.value)}
            placeholder="e.g. warm, direct, occasionally witty"
            className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
        </Field>

        <Field label="Response style">
          <select
            value={assistant.response_style}
            onChange={(e) => update('response_style', e.target.value)}
            className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
          >
            {RESPONSE_STYLES.map((style) => (
              <option key={style} value={style}>
                {style}
              </option>
            ))}
          </select>
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Provider">
            <select
              value={assistant.model_provider}
              onChange={(e) => {
                update('model_provider', e.target.value)
                update('model_name', null)
              }}
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
            >
              <option value="gemini">Gemini</option>
              <option value="openai">OpenAI</option>
            </select>
          </Field>

          <Field label="Model">
            <select
              value={assistant.model_name ?? ''}
              onChange={(e) => update('model_name', e.target.value || null)}
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
            >
              <option value="">Provider default</option>
              {(models[assistant.model_provider] ?? []).map((modelId) => (
                <option key={modelId} value={modelId}>
                  {modelId}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label={`Temperature (${assistant.temperature.toFixed(1)})`}>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={assistant.temperature}
              onChange={(e) => update('temperature', parseFloat(e.target.value))}
              className="w-full accent-[var(--color-accent)]"
            />
          </Field>

          <Field label="Max tokens">
            <input
              type="number"
              min={64}
              max={8192}
              value={assistant.max_tokens}
              onChange={(e) => update('max_tokens', parseInt(e.target.value, 10) || 0)}
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
            />
          </Field>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {isSaving ? 'Saving…' : 'Save changes'}
          </button>
          {savedAt && <span className="text-sm text-ink-muted">Saved.</span>}
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-ink">{label}</span>
      {children}
    </label>
  )
}
