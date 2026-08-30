import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type WorkspaceDocument } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

const STATUS_LABEL: Record<WorkspaceDocument['status'], string> = {
  pending: 'Pending',
  processing: 'Processing…',
  ready: 'Ready',
  failed: 'Failed',
}

const STATUS_CLASS: Record<WorkspaceDocument['status'], string> = {
  pending: 'text-ink-muted',
  processing: 'text-ink-muted',
  ready: 'text-accent',
  failed: 'text-danger',
}

function formatSize(bytes: number | null): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentsPage() {
  const { workspaceId = '' } = useParams()
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api
      .listDocuments(workspaceId)
      .then(setDocuments)
      .finally(() => setIsLoading(false))
  }, [workspaceId])

  async function handleFileSelected(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    setError(null)
    setIsUploading(true)
    try {
      const document = await api.uploadDocument(workspaceId, file)
      setDocuments((prev) => [document, ...prev])
    } catch {
      setError('Upload failed. Supported types: PDF, DOCX, TXT, Markdown.')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleDelete(documentId: string) {
    await api.deleteDocument(workspaceId, documentId)
    setDocuments((prev) => prev.filter((doc) => doc.id !== documentId))
  }

  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto px-6 py-10">
      <div className="mb-6 space-y-1">
        <h1 className="text-lg font-medium text-ink">Knowledge base</h1>
        <p className="text-sm text-ink-muted">
          Upload PDF, DOCX, TXT, or Markdown files. The assistant will cite them when relevant.
        </p>
      </div>

      <label className="mb-6 flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-line px-6 py-8 text-center transition-colors hover:border-accent">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={(e) => handleFileSelected(e.target.files)}
        />
        <span className="text-sm font-medium text-ink">
          {isUploading ? 'Uploading…' : 'Click to upload a document'}
        </span>
        <span className="mt-1 text-xs text-ink-muted">PDF, DOCX, TXT, MD</span>
      </label>

      {error && <p className="mb-4 text-sm text-danger">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : documents.length === 0 ? (
        <EmptyState title="No documents yet" description="Upload a file to give the assistant something to reference." />
      ) : (
        <ul className="space-y-2">
          {documents.map((document) => (
            <li
              key={document.id}
              className="flex items-center justify-between rounded-lg border border-line bg-surface px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{document.filename}</p>
                <p className="text-xs text-ink-muted">
                  {formatSize(document.size_bytes)} ·{' '}
                  <span className={STATUS_CLASS[document.status]}>{STATUS_LABEL[document.status]}</span>
                </p>
              </div>
              <button
                onClick={() => handleDelete(document.id)}
                className="ml-3 flex-shrink-0 text-xs text-ink-muted hover:text-danger"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
