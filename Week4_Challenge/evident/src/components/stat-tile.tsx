import type { LucideIcon } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function StatTile({
  icon: Icon,
  label,
  value,
  trend,
  trendDirection = 'up',
}: {
  icon: LucideIcon
  label: string
  value: string
  trend?: string
  trendDirection?: 'up' | 'down' | 'neutral'
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
      {trend && (
        <p
          className={cn(
            'mt-1 text-xs font-medium',
            trendDirection === 'up' && 'text-success',
            trendDirection === 'down' && 'text-destructive',
            trendDirection === 'neutral' && 'text-muted-foreground',
          )}
        >
          {trend}
        </p>
      )}
    </Card>
  )
}
