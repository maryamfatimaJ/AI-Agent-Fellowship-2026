import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type Workspace } from '../lib/api'
import { ConfirmDialog } from '../components/ConfirmDialog'

export function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [name, setName] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)
  const [isSavingRename, setIsSavingRename] = useState(false)
  const editInputRef = useRef<HTMLInputElement>(null)

  const [deletingWorkspace, setDeletingWorkspace] = useState<Workspace | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listWorkspaces()
      .then(setWorkspaces)
      .catch(() => setError('Could not load workspaces.'))
      .finally(() => setIsLoading(false))
  }, [])

  useEffect(() => {
    if (editingId) editInputRef.current?.focus()
  }, [editingId])

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

  function startRename(workspace: Workspace) {
    setEditingId(workspace.id)
    setEditValue(workspace.name)
    setRenameError(null)
  }

  function cancelRename() {
    setEditingId(null)
    setRenameError(null)
  }

  async function saveRename(workspaceId: string) {
    const trimmed = editValue.trim()
    if (!trimmed) {
      setRenameError('Workspace name cannot be empty.')
      return
    }
    setIsSavingRename(true)
    setRenameError(null)
    try {
      const updated = await api.renameWorkspace(workspaceId, trimmed)
      setWorkspaces((prev) => prev.map((w) => (w.id === workspaceId ? updated : w)))
      setEditingId(null)
    } catch (err) {
      setRenameError(err instanceof ApiError ? err.message : 'Could not rename workspace.')
    } finally {
      setIsSavingRename(false)
    }
  }

  function handleRenameKeyDown(event: KeyboardEvent<HTMLInputElement>, workspaceId: string) {
    if (event.key === 'Enter') {
      event.preventDefault()
      saveRename(workspaceId)
    } else if (event.key === 'Escape') {
      cancelRename()
    }
  }

  async function confirmDelete() {
    if (!deletingWorkspace) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await api.deleteWorkspace(deletingWorkspace.id)
      setWorkspaces((prev) => prev.filter((w) => w.id !== deletingWorkspace.id))
      setDeletingWorkspace(null)
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Could not delete workspace.')
    } finally {
      setIsDeleting(false)
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
          <li
            key={workspace.id}
            className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-3.5 transition-colors hover:border-accent"
          >
            {editingId === workspace.id ? (
              <div className="flex-1 space-y-1">
                <div className="flex gap-2">
                  <input
                    ref={editInputRef}
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => handleRenameKeyDown(e, workspace.id)}
                    className="flex-1 rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink focus:border-accent focus:outline-none"
                  />
                  <button
                    onClick={() => saveRename(workspace.id)}
                    disabled={isSavingRename}
                    className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button
                    onClick={cancelRename}
                    className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-accent"
                  >
                    Cancel
                  </button>
                </div>
                {renameError && <p className="text-xs text-danger">{renameError}</p>}
              </div>
            ) : (
              <>
                <Link to={`/workspaces/${workspace.id}`} className="min-w-0 flex-1">
                  <p className="truncate font-medium text-ink">{workspace.name}</p>
                  {workspace.description && (
                    <p className="truncate text-sm text-ink-muted">{workspace.description}</p>
                  )}
                </Link>
                <div className="flex flex-shrink-0 items-center gap-1">
                  <button
                    onClick={() => startRename(workspace)}
                    className="rounded-md px-2 py-1 text-xs text-ink-muted hover:text-ink"
                  >
                    Rename
                  </button>
                  <button
                    onClick={() => {
                      setDeletingWorkspace(workspace)
                      setDeleteError(null)
                    }}
                    className="rounded-md px-2 py-1 text-xs text-ink-muted hover:text-danger"
                  >
                    Delete
                  </button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>

      {deletingWorkspace && (
        <ConfirmDialog
          title={`Delete "${deletingWorkspace.name}"?`}
          description="This permanently deletes the workspace and everything in it — conversations, messages, documents, memory, prompts, and skills. This cannot be undone."
          confirmLabel="Delete workspace"
          isConfirming={isDeleting}
          onConfirm={confirmDelete}
          onCancel={() => setDeletingWorkspace(null)}
        />
      )}
      {deleteError && <p className="mt-3 text-sm text-danger">{deleteError}</p>}
    </div>
  )
}
