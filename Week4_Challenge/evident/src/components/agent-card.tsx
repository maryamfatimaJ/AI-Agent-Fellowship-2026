import { Clock } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { StatusBadge } from '@/components/status-badge'
import type { AgentNode } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

export function AgentCard({ agent, className }: { agent: AgentNode; className?: string }) {
  return (
    <Card
      className={cn(
        'p-5 transition-colors',
        agent.status === 'running' && 'border-primary/40 shadow-glow',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{agent.name}</p>
          <p className="text-xs text-muted-foreground">{agent.role}</p>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{agent.detail}</p>

      <div className="mt-4 space-y-1.5">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Progress</span>
          <span className="font-medium text-foreground">{agent.progress}%</span>
        </div>
        <Progress value={agent.progress} />
      </div>

      {(agent.startedAt || agent.tokensUsed) && (
        <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
          {agent.startedAt && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {agent.startedAt}
              {agent.finishedAt ? ` – ${agent.finishedAt}` : ''}
            </span>
          )}
          {agent.tokensUsed && <span>{agent.tokensUsed.toLocaleString()} tokens</span>}
        </div>
      )}
    </Card>
  )
}
