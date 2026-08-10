import { CheckCircle2, CircleDashed, Loader2, XCircle, PauseCircle } from 'lucide-react'

import { cn } from '@/lib/utils'

export type AgentStatus = 'waiting' | 'running' | 'completed' | 'failed' | 'paused'

const CONFIG: Record<AgentStatus, { label: string; icon: typeof CheckCircle2; className: string }> = {
  waiting: {
    label: 'Waiting',
    icon: CircleDashed,
    className: 'bg-muted text-muted-foreground',
  },
  running: {
    label: 'Running',
    icon: Loader2,
    className: 'bg-accent text-accent-foreground',
  },
  completed: {
    label: 'Completed',
    icon: CheckCircle2,
    className: 'bg-success/15 text-success',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    className: 'bg-destructive/15 text-destructive',
  },
  paused: {
    label: 'Paused',
    icon: PauseCircle,
    className: 'bg-warning/15 text-warning',
  },
}

export function StatusBadge({ status, className }: { status: AgentStatus; className?: string }) {
  const { label, icon: Icon, className: statusClassName } = CONFIG[status]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        statusClassName,
        className,
      )}
    >
      <Icon className={cn('h-3 w-3', status === 'running' && 'animate-spin')} />
      {label}
    </span>
  )
}
