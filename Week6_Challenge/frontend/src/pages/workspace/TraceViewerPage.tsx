import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type Trace } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

const STATUS_STYLE: Record<string, string> = {
  success: 'border-line text-ink-muted',
  retried: 'border-line text-ink-muted',
  degraded: 'border-line text-ink-muted',
  error: 'border-danger text-danger',
  timeout: 'border-danger text-danger',
}

const TRACE_TYPES = ['chat', 'skill', 'embedding', 'memory_extraction', 'tool_call', 'evaluation']
const STATUSES = ['success', 'error', 'timeout', 'retried', 'degraded']

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString()
}

interface Span {
  id?: string
  name: string
  started_at?: string
  duration_ms: number
  status: string
  error?: string | null
  metadata?: Record<string, unknown>
}

const SPAN_LABEL: Record<string, string> = {
  request: 'Request',
  input_validation: 'Input Validation',
  retrieval: 'Retrieval',
  agent_decision: 'Agent Decision',
  model_call: 'Model Call',
  tool_call: 'Tool Call',
  tool_result: 'Tool Result',
  memory_extraction: 'Memory Extraction',
  final_response: 'Final Response',
}

function SpanTimeline({ spans }: { spans: Span[] }) {
  return (
    <ol className="space-y-1.5">
      {spans.map((span, index) => (
        <li key={span.id ?? index} className="rounded-md border border-line-soft bg-canvas px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-ink">{SPAN_LABEL[span.name] ?? span.name}</span>
            <span
              className={`rounded-full border px-2 py-0.5 text-xs ${
                span.status === 'success' ? 'border-line text-ink-muted' : 'border-danger text-danger'
              }`}
            >
              {span.status}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-ink-faint">
            {span.duration_ms.toFixed(1)}ms
            {span.started_at ? ` · ${new Date(span.started_at).toLocaleTimeString()}` : ''}
          </p>
          {span.error && <p className="mt-0.5 text-xs text-danger">{span.error}</p>}
          {span.metadata && Object.keys(span.metadata).length > 0 && (
            <dl className="mt-1.5 space-y-0.5">
              {Object.entries(span.metadata).map(([key, value]) => (
                <div key={key} className="flex gap-1.5 text-xs">
                  <dt className="text-ink-faint">{key}:</dt>
                  <dd className="truncate text-ink-muted">
                    {Array.isArray(value) ? value.join(', ') || '—' : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </li>
      ))}
    </ol>
  )
}

export function TraceViewerPage() {
  const { workspaceId = '' } = useParams()
  const [traces, setTraces] = useState<Trace[]>([])
  const [total, setTotal] = useState(0)
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState<Trace | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setIsLoading(true)
    api
      .listTraces(workspaceId, {
        trace_type: typeFilter || undefined,
        status: statusFilter || undefined,
        limit: 100,
      })
      .then((result) => {
        setTraces(result.items)
        setTotal(result.total)
      })
      .finally(() => setIsLoading(false))
  }, [workspaceId, typeFilter, statusFilter])

  return (
    <div className="mx-auto flex h-full max-w-5xl gap-6 overflow-hidden px-6 py-10">
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="mb-4 space-y-1">
          <h1 className="text-lg font-medium text-ink">Trace Viewer</h1>
          <p className="text-sm text-ink-muted">{total} request{total === 1 ? '' : 's'} traced.</p>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink"
          >
            <option value="">All types</option>
            {TRACE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink"
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {isLoading ? (
          <EmptyState title="Loading traces…" />
        ) : traces.length === 0 ? (
          <EmptyState title="No traces yet" description="Send a chat message or run a skill to generate traces." />
        ) : (
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-canvas text-xs text-ink-muted">
                <tr>
                  <th className="py-1.5 pr-3">Time</th>
                  <th className="py-1.5 pr-3">Type</th>
                  <th className="py-1.5 pr-3">Model</th>
                  <th className="py-1.5 pr-3">Status</th>
                  <th className="py-1.5 pr-3">Latency</th>
                  <th className="py-1.5">Cost</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((trace) => (
                  <tr
                    key={trace.id}
                    onClick={() => setSelected(trace)}
                    className={`cursor-pointer border-t border-line-soft hover:bg-line-soft ${
                      selected?.id === trace.id ? 'bg-accent-soft' : ''
                    }`}
                  >
                    <td className="py-1.5 pr-3 text-ink-faint">{formatTimestamp(trace.created_at)}</td>
                    <td className="py-1.5 pr-3 text-ink">{trace.trace_type}</td>
                    <td className="py-1.5 pr-3 text-ink-muted">{trace.model ?? '—'}</td>
                    <td className="py-1.5 pr-3">
                      <span className={`rounded-full border px-2 py-0.5 text-xs ${STATUS_STYLE[trace.status] ?? ''}`}>
                        {trace.status}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 text-ink-muted">{Math.round(trace.latency_ms)}ms</td>
                    <td className="py-1.5 text-ink-muted">${trace.cost_usd.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <aside className="w-80 flex-shrink-0 overflow-y-auto border-l border-line pl-6">
        {!selected ? (
          <p className="text-sm text-ink-faint">Select a trace to see its detail.</p>
        ) : (
          <div className="space-y-4">
            <h2 className="text-sm font-medium text-ink">Trace detail</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-xs text-ink-muted">Trace ID</dt>
                <dd className="truncate text-ink">{selected.trace_id}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Type / Status</dt>
                <dd className="text-ink">
                  {selected.trace_type} / {selected.status}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Provider / Model</dt>
                <dd className="text-ink">
                  {selected.provider ?? '—'} / {selected.model ?? '—'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Latency</dt>
                <dd className="text-ink">{selected.latency_ms.toFixed(1)}ms</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Tokens</dt>
                <dd className="text-ink">
                  {selected.input_tokens} in / {selected.output_tokens} out
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Cost</dt>
                <dd className="text-ink">${selected.cost_usd.toFixed(6)}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Retries</dt>
                <dd className="text-ink">{selected.retry_count}</dd>
              </div>
              {selected.error_message && (
                <div>
                  <dt className="text-xs text-ink-muted">Error</dt>
                  <dd className="text-danger">{selected.error_message}</dd>
                </div>
              )}
              {selected.eval_case_id && (
                <div>
                  <dt className="text-xs text-ink-muted">Evaluation link</dt>
                  <dd className="truncate text-ink">
                    run {selected.evaluation_run_id ?? '—'} / case {selected.eval_case_id}
                  </dd>
                </div>
              )}
              {Array.isArray(selected.meta?.spans) && (selected.meta!.spans as Span[]).length > 0 && (
                <div>
                  <dt className="mb-1.5 text-xs text-ink-muted">Execution timeline</dt>
                  <dd>
                    <SpanTimeline spans={selected.meta!.spans as Span[]} />
                  </dd>
                </div>
              )}
              {selected.meta && Object.keys(selected.meta).length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-ink-muted">Raw trace metadata</summary>
                  <pre className="mt-1.5 overflow-x-auto rounded-md border border-line-soft bg-canvas p-2 text-ink-muted">
                    {JSON.stringify(selected.meta, null, 2)}
                  </pre>
                </details>
              )}
            </dl>
          </div>
        )}
      </aside>
    </div>
  )
}
