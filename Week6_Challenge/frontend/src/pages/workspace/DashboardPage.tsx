import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type DashboardData } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

const ACTIVITY_LABEL: Record<string, string> = {
  conversation: 'Conversation',
  document: 'Document',
  memory: 'Memory',
}

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return `${days}d ago`
}

export function DashboardPage() {
  const { workspaceId = '' } = useParams()
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    api
      .getDashboard(workspaceId)
      .then(setData)
      .finally(() => setIsLoading(false))
  }, [workspaceId])

  if (isLoading) return <EmptyState title="Loading dashboard…" />
  if (!data) return <EmptyState title="Could not load dashboard." />

  const stats = [
    { label: 'Conversations', value: data.counts.conversations },
    { label: 'Messages', value: data.counts.messages },
    { label: 'Documents', value: data.counts.documents },
    { label: 'Memory items', value: data.counts.memory_items },
    { label: 'Prompts', value: data.counts.prompt_templates },
    { label: 'Skills', value: data.counts.skills },
  ]

  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto px-6 py-10">
      <div className="mb-8 space-y-1">
        <h1 className="text-lg font-medium text-ink">Dashboard</h1>
        <p className="text-sm text-ink-muted">An overview of this workspace's activity.</p>
      </div>

      <div className="mb-8 grid grid-cols-3 gap-3 sm:grid-cols-6">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-lg border border-line bg-surface px-4 py-3.5">
            <p className="text-2xl font-medium text-ink">{stat.value}</p>
            <p className="mt-0.5 text-xs text-ink-muted">{stat.label}</p>
          </div>
        ))}
      </div>

      <div className="mb-8 rounded-lg border border-line bg-surface p-5">
        <h2 className="mb-3 text-sm font-medium text-ink">Model usage</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-lg font-medium text-ink">{data.usage.total_input_tokens.toLocaleString()}</p>
            <p className="text-xs text-ink-muted">Input tokens</p>
          </div>
          <div>
            <p className="text-lg font-medium text-ink">{data.usage.total_output_tokens.toLocaleString()}</p>
            <p className="text-xs text-ink-muted">Output tokens</p>
          </div>
          <div>
            <p className="text-lg font-medium text-ink">${data.usage.estimated_cost_usd.toFixed(4)}</p>
            <p className="text-xs text-ink-muted">Estimated cost</p>
          </div>
        </div>
        <p className="mt-3 text-xs text-ink-faint">
          Estimates based on approximate public pricing — not a billing-accurate figure.
        </p>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-ink">Recent activity</h2>
        {data.recent_activity.length === 0 ? (
          <EmptyState title="No activity yet" description="Start a conversation or upload a document to see activity here." />
        ) : (
          <ul className="space-y-1.5">
            {data.recent_activity.map((item, index) => (
              <li
                key={index}
                className="flex items-center justify-between rounded-md border border-line-soft bg-surface px-3.5 py-2.5"
              >
                <div className="flex items-center gap-2.5 truncate">
                  <span className="flex-shrink-0 rounded-full border border-line px-2 py-0.5 text-xs text-ink-muted">
                    {ACTIVITY_LABEL[item.type] ?? item.type}
                  </span>
                  <span className="truncate text-sm text-ink">{item.title}</span>
                </div>
                <span className="flex-shrink-0 text-xs text-ink-faint">{formatRelativeTime(item.timestamp)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
