import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, type Workspace } from '../lib/api'

export function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [name, setName] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listWorkspaces()
      .then(setWorkspaces)
      .catch(() => setError('Could not load workspaces.'))
      .finally(() => setIsLoading(false))
  }, [])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    setIsCreating(true)
    try {
      const workspace = await api.createWorkspace(name.trim())
      setWorkspaces((prev) => [...prev, workspace])
      setName('')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <div className="mb-8 space-y-1">
        <h1 className="text-xl font-medium text-ink">Your workspaces</h1>
        <p className="text-sm text-ink-muted">
          Each workspace keeps its own assistant, conversations, documents, and memory.
        </p>
      </div>

      <form onSubmit={handleCreate} className="mb-8 flex gap-2">
        <input
          type="text"
          placeholder="New workspace name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="flex-1 rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={isCreating}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          Create
        </button>
      </form>

      {isLoading && <p className="text-sm text-ink-muted">Loading…</p>}
      {error && <p className="text-sm text-danger">{error}</p>}

      {!isLoading && workspaces.length === 0 && (
        <div className="rounded-lg border border-dashed border-line px-6 py-10 text-center">
          <p className="text-sm text-ink-muted">No workspaces yet. Create your first one above.</p>
        </div>
      )}

      <ul className="space-y-2">
        {workspaces.map((workspace) => (
          <li key={workspace.id}>
            <Link
              to={`/workspaces/${workspace.id}`}
              className="block rounded-lg border border-line bg-surface px-4 py-3.5 transition-colors hover:border-accent"
            >
              <p className="font-medium text-ink">{workspace.name}</p>
              {workspace.description && <p className="text-sm text-ink-muted">{workspace.description}</p>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
