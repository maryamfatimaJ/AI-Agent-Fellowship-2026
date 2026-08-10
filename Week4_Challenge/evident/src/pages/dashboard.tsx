import { Link } from 'react-router-dom'
import { ArrowUpRight, FileSearch, FolderClock, GitBranch, ListChecks, Plus } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { StatusBadge } from '@/components/status-badge'
import { StatTile } from '@/components/stat-tile'
import { AgentCard } from '@/components/agent-card'
import { projects, pipelineAgents } from '@/lib/mock-data'

export default function DashboardPage() {
  const activeProject = projects[0]
  const runningAgent = pipelineAgents.find((a) => a.status === 'running')

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Welcome back, Maryam</h2>
          <p className="text-sm text-muted-foreground">Here&apos;s where your research projects stand.</p>
        </div>
        <Button className="gap-1.5">
          <Plus className="h-4 w-4" />
          New research
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile icon={FolderClock} label="Active projects" value="2" trend="+1 this week" />
        <StatTile icon={GitBranch} label="Agents running" value="1" trend="Analysis in progress" trendDirection="neutral" />
        <StatTile icon={FileSearch} label="Evidence collected" value="75" trend="+21 today" />
        <StatTile icon={ListChecks} label="Tasks completed" value="34 / 48" trend="71% complete" trendDirection="neutral" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Current run</CardTitle>
              <p className="mt-0.5 text-xs text-muted-foreground">{activeProject.title}</p>
            </div>
            <StatusBadge status={activeProject.status} />
          </CardHeader>
          <CardContent className="space-y-5">
            <p className="text-sm leading-relaxed text-muted-foreground">{activeProject.question}</p>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Overall progress</span>
                <span className="font-medium text-foreground">{activeProject.progress}%</span>
              </div>
              <Progress value={activeProject.progress} />
            </div>
            <div className="flex items-center gap-3 pt-1">
              <Button size="sm" variant="secondary" asChild>
                <Link to="/workflow">
                  View pipeline
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
              <Button size="sm" variant="ghost" asChild>
                <Link to="/evidence">Review evidence</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {runningAgent && (
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
              Agent running now
            </p>
            <AgentCard agent={runningAgent} />
          </div>
        )}
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">All projects</p>
          <Button variant="ghost" size="sm" className="text-xs text-muted-foreground">
            View all
          </Button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {projects.map((project) => (
            <Card key={project.id} className="flex flex-col p-5 transition-colors hover:border-primary/30">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold leading-snug text-foreground">{project.title}</p>
                <StatusBadge status={project.status} className="shrink-0" />
              </div>
              <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                {project.question}
              </p>
              <div className="mt-4 space-y-1.5">
                <Progress value={project.progress} />
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>{project.evidenceCount} evidence items</span>
                  <span>{project.updatedAt}</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
