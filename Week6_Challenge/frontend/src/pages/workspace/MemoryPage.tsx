import { useEffect, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { api, type MemoryEntry } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

export function MemoryPage() {
  const { workspaceId = '' } = useParams()
  const [entries, setEntries] = useState<MemoryEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [key, setKey] = useState('')
  const [value, setValue] = useState('')

  useEffect(() => {
    api
      .listMemory(workspaceId)
      .then(setEntries)
      .finally(() => setIsLoading(false))
  }, [workspaceId])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (!key.trim() || !value.trim()) return
    const entry = await api.createMemory(workspaceId, key.trim(), value.trim())
    setEntries((prev) => [entry, ...prev])
    setKey('')
    setValue('')
  }

  async function handleDelete(id: string) {
    await api.deleteMemory(workspaceId, id)
    setEntries((prev) => prev.filter((e) => e.id !== id))
  }

  const pinned = entries.filter((e) => e.pinned)
  const remembered = entries.filter((e) => !e.pinned)

  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto px-6 py-10">
      <div className="mb-6 space-y-1">
        <h1 className="text-lg font-medium text-ink">Memory</h1>
        <p className="text-sm text-ink-muted">
          Pin facts you want the assistant to always remember. It also remembers useful details from
          conversations on its own.
        </p>
      </div>

      <form onSubmit={handleCreate} className="mb-8 space-y-2 rounded-lg border border-line bg-surface p-4">
        <input
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Short label, e.g. timezone"
          className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
        />
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="What should the assistant remember?"
          rows={2}
          className="w-full resize-none rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
        >
          Pin to memory
        </button>
      </form>

      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : entries.length === 0 ? (
        <EmptyState
          title="Nothing remembered yet"
          description="Pin something above, or keep chatting — the assistant picks up useful details automatically."
        />
      ) : (
        <div className="space-y-6">
          {pinned.length > 0 && (
            <MemorySection title="Pinned" entries={pinned} onDelete={handleDelete} />
          )}
          {remembered.length > 0 && (
            <MemorySection title="Remembered automatically" entries={remembered} onDelete={handleDelete} />
          )}
        </div>
      )}
    </div>
  )
}

function MemorySection({
  title,
  entries,
  onDelete,
}: {
  title: string
  entries: MemoryEntry[]
  onDelete: (id: string) => void
}) {
  return (
    <div>
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-faint">{title}</h2>
      <ul className="space-y-2">
        {entries.map((entry) => (
          <li key={entry.id} className="flex items-start justify-between rounded-lg border border-line bg-surface px-4 py-3">
            <p className="text-sm text-ink">{entry.value}</p>
            <button
              onClick={() => onDelete(entry.id)}
              className="ml-3 flex-shrink-0 text-xs text-ink-muted hover:text-danger"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
