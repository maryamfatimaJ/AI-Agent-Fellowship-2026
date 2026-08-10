import { useMemo, useState } from 'react'
import { Search, SlidersHorizontal } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { StatusBadge } from '@/components/status-badge'
import { EmptyState } from '@/components/empty-state'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { tasks, type TaskRow } from '@/lib/mock-data'
import type { AgentStatus } from '@/components/status-badge'

const PRIORITY_VARIANT: Record<TaskRow['priority'], 'muted' | 'primary' | 'warning' | 'destructive'> = {
  Low: 'muted',
  Medium: 'primary',
  High: 'warning',
  Critical: 'destructive',
}

const STATUS_FILTERS: Array<{ value: AgentStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All statuses' },
  { value: 'waiting', label: 'Waiting' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'paused', label: 'Paused' },
  { value: 'failed', label: 'Failed' },
]

export default function TasksPage() {
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<AgentStatus | 'all'>('all')

  const filtered = useMemo(() => {
    return tasks.filter((t) => {
      const matchesQuery =
        query.trim() === '' ||
        t.task.toLowerCase().includes(query.toLowerCase()) ||
        t.id.toLowerCase().includes(query.toLowerCase())
      const matchesStatus = statusFilter === 'all' || t.status === statusFilter
      return matchesQuery && matchesStatus
    })
  }, [query, statusFilter])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tasks..."
            className="pl-8"
          />
        </div>

        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as AgentStatus | 'all')}>
          <SelectTrigger className="w-44">
            <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map((f) => (
              <SelectItem key={f.value} value={f.value}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <p className="ml-auto text-xs text-muted-foreground">
          {filtered.length} of {tasks.length} tasks
        </p>
      </div>

      <Card className="overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No tasks match your filters"
            description="Try a different search term or clear the status filter."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="px-5 py-3 font-medium">Task</th>
                  <th className="px-5 py-3 font-medium">Agent</th>
                  <th className="px-5 py-3 font-medium">Priority</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Progress</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((task) => (
                  <tr
                    key={task.id}
                    className="border-b border-border/60 last:border-0 hover:bg-secondary/30"
                  >
                    <td className="px-5 py-3.5">
                      <p className="font-medium text-foreground">{task.task}</p>
                      <p className="text-xs text-muted-foreground">{task.id}</p>
                    </td>
                    <td className="px-5 py-3.5 text-muted-foreground">{task.agent}</td>
                    <td className="px-5 py-3.5">
                      <Badge variant={PRIORITY_VARIANT[task.priority]}>{task.priority}</Badge>
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <Progress value={task.progress} className="w-24" />
                        <span className="w-8 text-xs text-muted-foreground">{task.progress}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
