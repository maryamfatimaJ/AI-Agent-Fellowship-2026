import { cn } from '@/lib/utils'

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="relative flex h-7 w-7 items-center justify-center rounded-lg bg-primary/15">
        <div className="h-2.5 w-2.5 rounded-[3px] bg-primary shadow-[0_0_12px_hsl(var(--primary)/0.7)]" />
      </div>
      <span className="text-[15px] font-semibold tracking-tight text-foreground">Evident</span>
    </div>
  )
}
