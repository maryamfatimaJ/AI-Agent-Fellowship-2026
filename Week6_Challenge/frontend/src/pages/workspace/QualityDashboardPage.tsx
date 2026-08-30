import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  api,
  type ComparisonResult,
  type EvaluationRun,
  type QualityOverview,
  type QualityPerformance,
  type QualityReliability,
} from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

const SERIES = [
  'var(--chart-series-1)',
  'var(--chart-series-2)',
  'var(--chart-series-3)',
  'var(--chart-series-4)',
  'var(--chart-series-5)',
  'var(--chart-series-6)',
]

type Tab = 'overview' | 'rag' | 'agent' | 'reliability' | 'performance' | 'comparison'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'rag', label: 'RAG' },
  { key: 'agent', label: 'Agent' },
  { key: 'reliability', label: 'Reliability' },
  { key: 'performance', label: 'Performance' },
  { key: 'comparison', label: 'Comparison' },
]

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3.5">
      <p className="text-2xl font-medium text-ink">{value}</p>
      <p className="mt-0.5 text-xs text-ink-muted">{label}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-faint">{hint}</p>}
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-5">
      <h2 className="mb-3 text-sm font-medium text-ink">{title}</h2>
      {children}
    </div>
  )
}

function fmtPct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`
}

function fmtNum(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

export function QualityDashboardPage() {
  const { workspaceId = '' } = useParams()
  const [tab, setTab] = useState<Tab>('overview')

  const [overview, setOverview] = useState<QualityOverview | null>(null)
  const [rag, setRag] = useState<Record<string, unknown> | null>(null)
  const [agent, setAgent] = useState<Record<string, unknown> | null>(null)
  const [reliability, setReliability] = useState<QualityReliability | null>(null)
  const [performance, setPerformance] = useState<QualityPerformance | null>(null)
  const [runs, setRuns] = useState<EvaluationRun[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)

  function loadAll() {
    setIsLoading(true)
    Promise.all([
      api.getQualityOverview(workspaceId),
      api.getQualityRag(workspaceId),
      api.getQualityAgent(workspaceId),
      api.getQualityReliability(workspaceId),
      api.getQualityPerformance(workspaceId),
      api.listEvaluationRuns(workspaceId),
    ])
      .then(([ov, r, a, rel, perf, evalRuns]) => {
        setOverview(ov)
        setRag(r)
        setAgent(a)
        setReliability(rel)
        setPerformance(perf)
        setRuns(evalRuns.items)
      })
      .finally(() => setIsLoading(false))
  }

  useEffect(loadAll, [workspaceId])

  async function handleRunEvaluation() {
    setIsRunning(true)
    try {
      await api.runEvaluation(workspaceId, { name: 'dashboard-triggered run', limit: 15 })
      loadAll()
    } finally {
      setIsRunning(false)
    }
  }

  if (isLoading) return <EmptyState title="Loading quality dashboard…" />

  return (
    <div className="mx-auto h-full max-w-4xl overflow-y-auto px-6 py-10">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-lg font-medium text-ink">Quality Dashboard</h1>
          <p className="text-sm text-ink-muted">Evaluation, RAG, agent, reliability, and cost metrics.</p>
        </div>
        <button
          onClick={handleRunEvaluation}
          disabled={isRunning}
          className="flex-shrink-0 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {isRunning ? 'Running…' : 'Run evaluation (15 cases)'}
        </button>
      </div>

      <div className="mb-6 flex flex-wrap gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-t-md px-3 py-2 text-sm ${
              tab === t.key ? 'border-b-2 border-accent text-ink' : 'text-ink-muted hover:text-ink'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && overview && <OverviewTab overview={overview} />}
      {tab === 'rag' && <RagTab rag={rag} />}
      {tab === 'agent' && <AgentTab agent={agent} />}
      {tab === 'reliability' && reliability && <ReliabilityTab reliability={reliability} />}
      {tab === 'performance' && performance && <PerformanceTab performance={performance} />}
      {tab === 'comparison' && <ComparisonTab workspaceId={workspaceId} runs={runs} />}
    </div>
  )
}

function OverviewTab({ overview }: { overview: QualityOverview }) {
  if (!overview.latest_run_id) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Requests" value={String(overview.request_count)} />
          <StatTile label="Cost" value={`$${overview.cost_usd.toFixed(4)}`} />
          <StatTile label="Failure rate" value={fmtPct(overview.failure_rate)} />
          <StatTile label="Guardrail triggers" value={String(overview.guardrail_trigger_count)} />
        </div>
        <EmptyState
          title="No evaluation run yet"
          description="Click 'Run evaluation' above to run a slice of the 68-case dataset and populate task success rate, judge score, RAG, and agent metrics."
        />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatTile label="Task success rate" value={fmtPct(overview.task_success_rate)} hint={`n=${overview.n_cases ?? 0}`} />
      <StatTile label="Avg judge score" value={fmtNum(overview.avg_judge_score, 2)} hint="1–5 scale" />
      <StatTile label="Failure rate" value={fmtPct(overview.failure_rate)} />
      <StatTile label="Guardrail triggers" value={String(overview.guardrail_trigger_count)} />
      <StatTile label="Requests" value={String(overview.request_count)} />
      <StatTile label="Cost" value={`$${overview.cost_usd.toFixed(4)}`} />
      <StatTile label="P95 latency" value={`${fmtNum(overview.latency_ms.p95)}ms`} />
      <StatTile label="Total tokens" value={overview.token_usage.total.toLocaleString()} />
    </div>
  )
}

function RagTab({ rag }: { rag: Record<string, unknown> | null }) {
  if (!rag || Object.keys(rag).length === 0) {
    return <EmptyState title="No RAG metrics yet" description="Run an evaluation that includes rag-category cases." />
  }
  const failureData = [
    { name: 'Retrieval failures', value: Number(rag.retrieval_failures ?? 0) },
    { name: 'Generation failures', value: Number(rag.generation_failures ?? 0) },
  ]
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatTile label="Retrieval hit rate" value={fmtPct(rag.retrieval_hit_rate as number)} />
        <StatTile label="Context relevance" value={fmtPct(rag.avg_context_relevance as number)} />
        <StatTile label="Groundedness" value={fmtPct(rag.avg_groundedness as number)} />
        <StatTile label="Citation correctness" value={fmtPct(rag.citation_correctness_rate as number)} />
        <StatTile label="Unsupported claim rate" value={fmtPct(rag.unsupported_claim_rate as number)} />
        <StatTile label="Cases evaluated" value={String(rag.n_cases ?? 0)} />
      </div>
      <Panel title="Retrieval vs. generation failures">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={failureData} layout="vertical" margin={{ left: 24 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" horizontal={false} />
            <XAxis type="number" stroke="var(--chart-axis)" fontSize={12} allowDecimals={false} />
            <YAxis type="category" dataKey="name" stroke="var(--chart-axis)" fontSize={12} width={140} />
            <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-line)', fontSize: 12 }} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {failureData.map((_entry, index) => (
                <Cell key={index} fill={SERIES[index % SERIES.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  )
}

function AgentTab({ agent }: { agent: Record<string, unknown> | null }) {
  if (!agent || Object.keys(agent).length === 0) {
    return <EmptyState title="No agent metrics yet" description="Run an evaluation that includes tool_use-category cases." />
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <StatTile label="Tool selection accuracy" value={fmtPct(agent.tool_selection_accuracy as number)} />
      <StatTile label="Tool argument accuracy" value={fmtPct(agent.tool_argument_accuracy as number)} />
      <StatTile label="Task completion rate" value={fmtPct(agent.task_completion_rate as number)} />
      <StatTile label="Avg loop count" value={fmtNum(agent.avg_loop_count as number, 1)} />
      <StatTile label="Loop-limit hit rate" value={fmtPct(agent.loop_limit_hit_rate as number)} />
      <StatTile label="Recovery rate" value={fmtPct(agent.recovery_rate as number)} />
    </div>
  )
}

function ReliabilityTab({ reliability }: { reliability: QualityReliability }) {
  const typeData = useMemo(
    () => Object.entries(reliability.guardrail_events_by_type).map(([name, value]) => ({ name, value })),
    [reliability]
  )
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Successful requests" value={String(reliability.successful_requests)} />
        <StatTile label="Failed requests" value={String(reliability.failed_requests)} />
        <StatTile label="Retry rate" value={fmtPct(reliability.retry_rate)} />
        <StatTile label="Timeout rate" value={fmtPct(reliability.timeout_rate)} />
        <StatTile label="Error rate" value={fmtPct(reliability.error_rate)} />
        <StatTile label="Degraded rate" value={fmtPct(reliability.degraded_rate)} />
        <StatTile label="Blocked" value={String(reliability.blocked_count)} />
        <StatTile label="Flagged" value={String(reliability.flagged_count)} />
        <StatTile label="Sanitized" value={String(reliability.sanitized_count)} />
      </div>
      {typeData.length > 0 && (
        <Panel title="Guardrail events by type">
          <ResponsiveContainer width="100%" height={Math.max(160, typeData.length * 36)}>
            <BarChart data={typeData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" horizontal={false} />
              <XAxis type="number" stroke="var(--chart-axis)" fontSize={12} allowDecimals={false} />
              <YAxis type="category" dataKey="name" stroke="var(--chart-axis)" fontSize={12} width={160} />
              <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-line)', fontSize: 12 }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {typeData.map((_entry, index) => (
                  <Cell key={index} fill={SERIES[index % SERIES.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}
    </div>
  )
}

function PerformanceTab({ performance }: { performance: QualityPerformance }) {
  const latencyData = [
    { name: 'Mean', value: performance.latency_ms.mean ?? 0 },
    { name: 'P50', value: performance.latency_ms.p50 ?? 0 },
    { name: 'P95', value: performance.latency_ms.p95 ?? 0 },
    { name: 'P99', value: performance.latency_ms.p99 ?? 0 },
  ]
  const costByModel = Object.entries(performance.by_model).map(([name, stats]) => ({
    name,
    cost: stats.total_cost_usd,
  }))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Requests" value={String(performance.n_requests)} />
        <StatTile label="Total cost" value={`$${performance.cost.total_usd.toFixed(4)}`} />
        <StatTile label="Cost / request" value={`$${performance.cost.per_request_usd.toFixed(6)}`} />
        <StatTile
          label="Cost / successful task"
          value={performance.cost.per_successful_task_usd !== null ? `$${performance.cost.per_successful_task_usd.toFixed(6)}` : '—'}
        />
        <StatTile label="Input tokens" value={performance.tokens.input.toLocaleString()} />
        <StatTile label="Output tokens" value={performance.tokens.output.toLocaleString()} />
        <StatTile label="Total tokens" value={performance.tokens.total.toLocaleString()} />
        <StatTile label="Median latency" value={`${fmtNum(performance.latency_ms.median)}ms`} />
        <StatTile label="Retry rate" value={fmtPct(performance.reliability.retry_rate)} />
        <StatTile label="Timeout rate" value={fmtPct(performance.reliability.timeout_rate)} />
        <StatTile label="Error rate" value={fmtPct(performance.reliability.error_rate)} />
      </div>

      <Panel title="Latency (ms)">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={latencyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="name" stroke="var(--chart-axis)" fontSize={12} />
            <YAxis stroke="var(--chart-axis)" fontSize={12} />
            <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-line)', fontSize: 12 }} />
            <Bar dataKey="value" fill="var(--chart-series-1)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      {costByModel.length > 0 && (
        <Panel title="Cost by model">
          <ResponsiveContainer width="100%" height={Math.max(160, costByModel.length * 40)}>
            <BarChart data={costByModel} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" horizontal={false} />
              <XAxis type="number" stroke="var(--chart-axis)" fontSize={12} />
              <YAxis type="category" dataKey="name" stroke="var(--chart-axis)" fontSize={12} width={140} />
              <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-line)', fontSize: 12 }} />
              <Bar dataKey="cost" fill="var(--chart-series-3)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {performance.bottlenecks.length > 0 && (
        <Panel title="Slowest stages (avg latency)">
          <ul className="space-y-1.5">
            {performance.bottlenecks.map((b) => (
              <li key={b.stage} className="flex items-center justify-between rounded-md border border-line-soft px-3 py-2 text-sm">
                <span className="text-ink">{b.stage}</span>
                <span className="text-ink-muted">{b.avg_latency_ms}ms avg · n={b.n_requests}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  )
}

function ComparisonTab({ workspaceId, runs }: { workspaceId: string; runs: EvaluationRun[] }) {
  const [runA, setRunA] = useState('')
  const [runB, setRunB] = useState('')
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function compare() {
    setError(null)
    setResult(null)
    try {
      const comparison = await api.compareEvaluationRuns(workspaceId, runA, runB)
      setResult(comparison)
    } catch {
      setError('Could not compare these runs — pick two completed runs.')
    }
  }

  if (runs.length < 2) {
    return (
      <EmptyState
        title="Need at least 2 evaluation runs"
        description="Run the evaluation a couple of times (e.g. with different prompt versions or models) to compare them here."
      />
    )
  }

  const chartData = result
    ? [
        { name: 'Improved', value: result.improved },
        { name: 'Regressed', value: result.regressed },
        { name: 'Unchanged', value: result.unchanged },
      ]
    : []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-ink-muted">Run A (baseline)</span>
          <select
            value={runA}
            onChange={(e) => setRunA(e.target.value)}
            className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink"
          >
            <option value="">Select…</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.provider}/{r.model})
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-ink-muted">Run B (candidate)</span>
          <select
            value={runB}
            onChange={(e) => setRunB(e.target.value)}
            className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink"
          >
            <option value="">Select…</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.provider}/{r.model})
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={compare}
          disabled={!runA || !runB}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          Compare
        </button>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <StatTile label="Improved" value={String(result.improved)} />
            <StatTile label="Regressed" value={String(result.regressed)} />
            <StatTile label="Unchanged" value={String(result.unchanged)} />
          </div>
          <Panel title="Case outcomes">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="name" stroke="var(--chart-axis)" fontSize={12} />
                <YAxis stroke="var(--chart-axis)" fontSize={12} allowDecimals={false} />
                <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-line)', fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="value" name="Cases" fill="var(--chart-series-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Panel>
          <Panel title="Per-case detail">
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-surface text-xs text-ink-muted">
                  <tr>
                    <th className="py-1.5 pr-3">Case</th>
                    <th className="py-1.5 pr-3">Category</th>
                    <th className="py-1.5 pr-3">Status</th>
                    <th className="py-1.5 pr-3">A score</th>
                    <th className="py-1.5">B score</th>
                  </tr>
                </thead>
                <tbody>
                  {result.cases.map((c) => (
                    <tr key={c.case_id} className="border-t border-line-soft">
                      <td className="py-1.5 pr-3 text-ink">{c.case_id}</td>
                      <td className="py-1.5 pr-3 text-ink-muted">{c.category}</td>
                      <td className="py-1.5 pr-3">
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs ${
                            c.status === 'improved'
                              ? 'border-line text-ink'
                              : c.status === 'regressed'
                                ? 'border-danger text-danger'
                                : 'border-line-soft text-ink-faint'
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="py-1.5 pr-3 text-ink-muted">{c.run_a_judge_score ?? '—'}</td>
                      <td className="py-1.5 text-ink-muted">{c.run_b_judge_score ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}
