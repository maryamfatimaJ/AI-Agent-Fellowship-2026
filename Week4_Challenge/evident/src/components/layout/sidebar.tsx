import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  GitBranch,
  ListChecks,
  FileSearch,
  ScrollText,
  FileText,
  Plus,
  Settings,
} from 'lucide-react'

import { Logo } from '@/components/layout/logo'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/workflow', label: 'Workflow', icon: GitBranch },
  { to: '/tasks', label: 'Tasks', icon: ListChecks },
  { to: '/evidence', label: 'Evidence', icon: FileSearch },
  { to: '/logs', label: 'Logs', icon: ScrollText },
  { to: '/reports', label: 'Reports', icon: FileText },
]

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-border bg-card/60 backdrop-blur-xl lg:flex">
      <div className="flex h-16 items-center px-5">
        <Logo />
      </div>

      <div className="px-3">
        <Button size="sm" className="w-full justify-start gap-2 font-medium">
          <Plus className="h-4 w-4" />
          New research
        </Button>
      </div>

      <nav className="mt-4 flex-1 space-y-0.5 px-3">
        <p className="px-2 pb-2 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
          Workspace
        </p>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground',
                isActive && 'bg-secondary text-foreground',
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={cn(
                    'h-4 w-4 text-muted-foreground/70 transition-colors group-hover:text-foreground',
                    isActive && 'text-primary',
                  )}
                />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3">
        <button className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground">
          <Settings className="h-4 w-4 text-muted-foreground/70" />
          Settings
        </button>
      </div>
    </aside>
  )
}
