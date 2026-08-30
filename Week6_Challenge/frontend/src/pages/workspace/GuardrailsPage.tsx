import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type GuardrailEvent, type PendingAction } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

const ACTION_STYLE: Record<string, string> = {
  blocked: 'border-danger text-danger',
  flagged: 'border-line text-ink-muted',
  sanitized: 'border-line text-ink-muted',
  approved: 'border-accent text-accent',
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString()
}

export function GuardrailsPage() {
  const { workspaceId = '' } = useParams()
  const [events, setEvents] = useState<GuardrailEvent[]>([])
  const [pending, setPending] = useState<PendingAction[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [decidingId, setDecidingId] = useState<string | null>(null)

  function load() {
    setIsLoading(true)
    Promise.all([
      api.listGuardrailEvents(workspaceId, { limit: 100 }),
      api.listPendingActions(workspaceId, 'pending'),
    ])
      .then(([eventResult, pendingResult]) => {
        setEvents(eventResult.items)
        setPending(pendingResult)
      })
      .finally(() => setIsLoading(false))
  }

  useEffect(load, [workspaceId])

  async function decide(actionId: string, approve: boolean) {
    setDecidingId(actionId)
    try {
      await api.decidePendingAction(workspaceId, actionId, approve)
      load()
    } finally {
      setDecidingId(null)
    }
  }

  if (isLoading) return <EmptyState title="Loading guardrails…" />

  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto px-6 py-10">
      <div className="mb-8 space-y-1">
        <h1 className="text-lg font-medium text-ink">Guardrails</h1>
        <p className="text-sm text-ink-muted">Prompt-injection detections, secret redactions, and high-risk tool approvals.</p>
      </div>

      <div className="mb-8">
        <h2 className="mb-3 text-sm font-medium text-ink">Pending approvals</h2>
        {pending.length === 0 ? (
          <p className="text-sm text-ink-faint">Nothing awaiting approval.</p>
        ) : (
          <ul className="space-y-2">
            {pending.map((action) => (
              <li key={action.id} className="rounded-md border border-line bg-surface p-3.5">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium text-ink">{action.tool_name}</span>
                  <span className="rounded-full border border-danger px-2 py-0.5 text-xs text-danger">
                    {action.risk_level} risk
                  </span>
                </div>
                <pre className="mb-3 overflow-x-auto rounded-md border border-line-soft bg-canvas p-2 text-xs text-ink-muted">
                  {JSON.stringify(action.tool_args, null, 2)}
                </pre>
                <div className="flex gap-2">
                  <button
                    onClick={() => decide(action.id, true)}
                    disabled={decidingId === action.id}
                    className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => decide(action.id, false)}
                    disabled={decidingId === action.id}
                    className="rounded-md border border-line px-3 py-1.5 text-xs text-ink disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-ink">Event log</h2>
        {events.length === 0 ? (
          <EmptyState title="No guardrail events yet" />
        ) : (
          <ul className="space-y-1.5">
            {events.map((event) => (
              <li
                key={event.id}
                className="rounded-md border border-line-soft bg-surface px-3.5 py-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 truncate">
                    <span className={`flex-shrink-0 rounded-full border px-2 py-0.5 text-xs ${ACTION_STYLE[event.action] ?? ''}`}>
                      {event.action}
                    </span>
                    <span className="truncate text-sm text-ink">{event.guardrail_type}</span>
                    <span className="flex-shrink-0 text-xs text-ink-faint">({event.direction})</span>
                  </div>
                  <span className="flex-shrink-0 text-xs text-ink-faint">{formatTimestamp(event.created_at)}</span>
                </div>
                {event.detail && (
                  <p className="mt-1 truncate text-xs text-ink-muted">{JSON.stringify(event.detail)}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
