import { useState } from 'react'
import { ArrowRight } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AgentCard } from '@/components/agent-card'
import { ApprovalModal } from '@/components/approval-modal'
import { StatusBadge } from '@/components/status-badge'
import { pipelineAgents } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

export default function WorkflowPage() {
  const [approvalOpen, setApprovalOpen] = useState(false)

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Vertical SaaS market entry</h2>
          <p className="text-sm text-muted-foreground">
            Should we enter the vertical SaaS market for healthcare scheduling in Q1 2027?
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setApprovalOpen(true)}>
          Review flagged conflict
        </Button>
      </div>

      <Card className="overflow-x-auto p-6">
        <div className="flex min-w-max items-stretch gap-2">
          {pipelineAgents.map((agent, i) => (
            <div key={agent.id} className="flex items-center">
              <div
                className={cn(
                  'flex w-44 flex-col items-center gap-2 rounded-xl border border-border bg-secondary/30 px-4 py-4 text-center',
                  agent.status === 'running' && 'border-primary/50 shadow-glow',
                  agent.status === 'completed' && 'border-success/30',
                  agent.status === 'failed' && 'border-destructive/30',
                )}
              >
                <span className="text-sm font-semibold text-foreground">{agent.name}</span>
                <span className="text-[11px] text-muted-foreground">{agent.role}</span>
                <StatusBadge status={agent.status} />
              </div>
              {i < pipelineAgents.length - 1 && (
                <ArrowRight className="mx-2 h-4 w-4 shrink-0 text-muted-foreground/40" />
              )}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
        {pipelineAgents.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Supervisor decisions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-start gap-3 rounded-lg border border-border bg-secondary/30 p-3">
            <Badge variant="success" className="mt-0.5 shrink-0">
              Routed
            </Badge>
            <p className="text-sm text-muted-foreground">
              Split the question into source discovery, market sizing, competitive risk, and regulatory
              risk sub-tasks — routed to Research and Analysis agents.
            </p>
          </div>
          <div className="flex items-start gap-3 rounded-lg border border-border bg-secondary/30 p-3">
            <Badge variant="warning" className="mt-0.5 shrink-0">
              Escalated
            </Badge>
            <p className="text-sm text-muted-foreground">
              Escalated a churn-benchmark conflict from Analysis to Critic for adversarial review before
              it reaches the Writer agent.
            </p>
          </div>
        </CardContent>
      </Card>

      <ApprovalModal open={approvalOpen} onOpenChange={setApprovalOpen} onApprove={() => setApprovalOpen(false)} onReject={() => setApprovalOpen(false)} />
    </div>
  )
}
