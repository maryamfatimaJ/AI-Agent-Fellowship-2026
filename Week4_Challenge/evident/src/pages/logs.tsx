import { AlertCircle, Info, Terminal, TriangleAlert } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { logEntries, type LogLevel } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

const LEVEL_CONFIG: Record<LogLevel, { icon: typeof Info; className: string; label: string }> = {
  info: { icon: Info, className: 'bg-secondary text-muted-foreground', label: 'Info' },
  tool: { icon: Terminal, className: 'bg-accent text-accent-foreground', label: 'Tool' },
  warning: { icon: TriangleAlert, className: 'bg-warning/15 text-warning', label: 'Warning' },
  error: { icon: AlertCircle, className: 'bg-destructive/15 text-destructive', label: 'Error' },
}

export default function LogsPage() {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(LEVEL_CONFIG) as LogLevel[]).map((level) => {
          const count = logEntries.filter((l) => l.level === level).length
          const config = LEVEL_CONFIG[level]
          return (
            <Badge key={level} className={cn('gap-1.5', config.className)}>
              <config.icon className="h-3 w-3" />
              {config.label}
              <span className="opacity-70">{count}</span>
            </Badge>
          )
        })}
      </div>

      <Card className="p-6">
        <div className="relative space-y-6 before:absolute before:bottom-0 before:left-[15px] before:top-1 before:w-px before:bg-border">
          {logEntries.map((entry) => {
            const config = LEVEL_CONFIG[entry.level]
            return (
              <div key={entry.id} className="relative flex gap-4 pl-0">
                <div
                  className={cn(
                    'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-4 border-background',
                    config.className,
                  )}
                >
                  <config.icon className="h-3.5 w-3.5" />
                </div>
                <div className="flex-1 pb-1 pt-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-muted-foreground">{entry.time}</span>
                    <Badge variant="muted">{entry.agent}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-foreground">{entry.message}</p>
                  {entry.meta && (
                    <p className="mt-1 rounded-md bg-secondary/50 px-2 py-1 font-mono text-xs text-muted-foreground">
                      {entry.meta}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}
