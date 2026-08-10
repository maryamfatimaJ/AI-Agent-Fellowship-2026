import { useState } from 'react'
import { ExternalLink, FileSearch, Quote } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { evidenceItems, type EvidenceItem } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

function confidenceVariant(confidence: number): 'success' | 'warning' | 'destructive' {
  if (confidence >= 75) return 'success'
  if (confidence >= 55) return 'warning'
  return 'destructive'
}

export default function EvidencePage() {
  const [selected, setSelected] = useState<EvidenceItem>(evidenceItems[0])

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        {evidenceItems.map((item) => (
          <Card
            key={item.id}
            onClick={() => setSelected(item)}
            className={cn(
              'cursor-pointer p-5 transition-colors hover:border-primary/30',
              selected.id === item.id && 'border-primary/50 shadow-glow',
            )}
          >
            <div className="flex items-start justify-between gap-4">
              <p className="text-sm font-semibold leading-snug text-foreground">{item.claim}</p>
              <Badge variant={confidenceVariant(item.confidence)} className="shrink-0">
                {item.confidence}% confidence
              </Badge>
            </div>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <FileSearch className="h-3 w-3" />
              {item.source}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {item.tags.map((tag) => (
                <Badge key={tag} variant="muted">
                  {tag}
                </Badge>
              ))}
              <span className="ml-auto text-xs text-muted-foreground">{item.agent} agent · {item.collectedAt}</span>
            </div>
          </Card>
        ))}
      </div>

      <div className="lg:sticky lg:top-24 lg:self-start">
        <Card>
          <CardHeader>
            <CardTitle>Evidence detail</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/70">Claim</p>
              <p className="mt-1.5 text-sm leading-relaxed text-foreground">{selected.claim}</p>
            </div>

            <Separator />

            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/70">Confidence</p>
              <div className="mt-1.5 flex items-center gap-2">
                <Badge variant={confidenceVariant(selected.confidence)}>{selected.confidence}%</Badge>
                <span className="text-xs text-muted-foreground">from {selected.agent} agent</span>
              </div>
            </div>

            <Separator />

            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/70">Source</p>
              <a
                href={`https://${selected.sourceUrl}`}
                target="_blank"
                rel="noreferrer"
                className="mt-1.5 flex items-center gap-1.5 text-sm text-primary hover:underline"
              >
                {selected.source}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <Separator />

            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground/70">Excerpt</p>
              <div className="mt-1.5 flex gap-2 rounded-lg border border-border bg-secondary/40 p-3">
                <Quote className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <p className="text-sm italic leading-relaxed text-muted-foreground">{selected.excerpt}</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 pt-1">
              {selected.tags.map((tag) => (
                <Badge key={tag} variant="muted">
                  {tag}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
