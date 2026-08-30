import { useEffect, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { api, PROMPT_CATEGORIES, type PromptTemplate } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

export function PromptsPage() {
  const { workspaceId = '' } = useParams()
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [isCreating, setIsCreating] = useState(false)
  const [name, setName] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState<string>('custom')

  useEffect(() => {
    api
      .listPrompts(workspaceId)
      .then(setPrompts)
      .finally(() => setIsLoading(false))
  }, [workspaceId])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || !content.trim()) return
    const prompt = await api.createPrompt(workspaceId, name.trim(), content.trim(), category)
    setPrompts((prev) => [prompt, ...prev])
    setName('')
    setContent('')
    setIsCreating(false)
  }

  async function handleDelete(id: string) {
    await api.deletePrompt(workspaceId, id)
    setPrompts((prev) => prev.filter((p) => p.id !== id))
  }

  const visible = activeCategory === 'all' ? prompts : prompts.filter((p) => p.category === activeCategory)

  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto px-6 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-lg font-medium text-ink">Prompt library</h1>
          <p className="text-sm text-ink-muted">Reusable prompts you can drop straight into any chat.</p>
        </div>
        <button
          onClick={() => setIsCreating((prev) => !prev)}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-accent hover:text-accent"
        >
          {isCreating ? 'Cancel' : '+ New prompt'}
        </button>
      </div>

      {isCreating && (
        <form onSubmit={handleCreate} className="mb-6 space-y-2 rounded-lg border border-line bg-surface p-4">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Prompt name"
            className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Prompt content"
            rows={3}
            className="w-full resize-none rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
          <div className="flex items-center gap-2">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink focus:border-accent focus:outline-none"
            >
              {PROMPT_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Save
            </button>
          </div>
        </form>
      )}

      <div className="mb-5 flex flex-wrap gap-1.5">
        {['all', ...PROMPT_CATEGORIES].map((c) => (
          <button
            key={c}
            onClick={() => setActiveCategory(c)}
            className={`rounded-full border px-2.5 py-1 text-xs ${
              activeCategory === c
                ? 'border-accent bg-accent-soft text-ink'
                : 'border-line text-ink-muted hover:text-ink'
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : visible.length === 0 ? (
        <EmptyState title="No prompts in this category" />
      ) : (
        <ul className="space-y-2">
          {visible.map((prompt) => (
            <li key={prompt.id} className="rounded-lg border border-line bg-surface p-4">
              <div className="mb-1 flex items-start justify-between gap-2">
                <p className="font-medium text-ink">{prompt.name}</p>
                <button onClick={() => handleDelete(prompt.id)} className="text-xs text-ink-muted hover:text-danger">
                  Delete
                </button>
              </div>
              <p className="mb-2 whitespace-pre-wrap text-sm text-ink-muted">{prompt.content}</p>
              <span className="rounded-full border border-line-soft px-2 py-0.5 text-xs text-ink-faint">
                {prompt.category}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
