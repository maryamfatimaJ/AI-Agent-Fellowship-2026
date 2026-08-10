import { AlertTriangle } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface ApprovalModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onApprove?: () => void
  onReject?: () => void
}

export function ApprovalModal({ open, onOpenChange, onApprove, onReject }: ApprovalModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-warning/15">
            <AlertTriangle className="h-5 w-5 text-warning" />
          </div>
          <DialogTitle className="mt-3">Critic flagged a conflict for review</DialogTitle>
          <DialogDescription>
            The Critic agent found conflicting evidence and needs your decision before the Writer agent
            proceeds.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-lg border border-border bg-secondary/40 p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-foreground">Churn benchmark conflict</p>
            <Badge variant="warning">48% confidence</Badge>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Two sources report 4.1% monthly churn while a third reports 6.8%, using different segment
            definitions. The Writer agent would otherwise average these into a single figure.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onReject}>
            Send back to Analysis
          </Button>
          <Button onClick={onApprove}>Approve with caveat noted</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
