import { useLocation } from 'react-router-dom'
import { Bell, Search } from 'lucide-react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

const PAGE_META: Record<string, { title: string; description: string }> = {
  '/dashboard': { title: 'Dashboard', description: 'Overview of your active research projects' },
  '/workflow': { title: 'Workflow', description: 'Live multi-agent pipeline for the current project' },
  '/tasks': { title: 'Tasks', description: 'All sub-tasks assigned across agents' },
  '/evidence': { title: 'Evidence', description: 'Claims and sources gathered by the pipeline' },
  '/logs': { title: 'Logs', description: 'Execution timeline and agent activity' },
  '/reports': { title: 'Reports', description: 'Final decision briefs and exports' },
}

export function Navbar() {
  const location = useLocation()
  const meta = PAGE_META[location.pathname] ?? { title: 'Evident', description: '' }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-border bg-background/80 px-6 backdrop-blur-xl">
      <div className="flex-1 min-w-0">
        <h1 className="truncate text-[15px] font-semibold text-foreground">{meta.title}</h1>
        <p className="truncate text-xs text-muted-foreground">{meta.description}</p>
      </div>

      <div className="hidden max-w-xs flex-1 items-center md:flex">
        <div className="relative w-full">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search projects, evidence..." className="h-8 bg-secondary/40 pl-8 text-xs" />
        </div>
      </div>

      <Button variant="ghost" size="icon" className="relative">
        <Bell className="h-4 w-4 text-muted-foreground" />
        <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-primary" />
      </Button>

      <Avatar className="h-8 w-8 border border-border">
        <AvatarFallback>MF</AvatarFallback>
      </Avatar>
    </header>
  )
}
