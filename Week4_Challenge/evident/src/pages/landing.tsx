import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ArrowUpRight, GitBranch, Layers, ShieldCheck, Sparkles } from 'lucide-react'

import { Logo } from '@/components/layout/logo'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card } from '@/components/ui/card'
import { examplePrompts } from '@/lib/mock-data'

const PIPELINE = ['Supervisor', 'Research', 'Analysis', 'Critic', 'Writer']

const FEATURES = [
  {
    icon: Layers,
    title: 'Structured, not conversational',
    description:
      'Every question decomposes into a visible pipeline of tasks, sources, and claims — not a single chat thread.',
  },
  {
    icon: ShieldCheck,
    title: 'Evidence-first outputs',
    description:
      'Every claim in a report links back to a source and a confidence score. Nothing ships unverified.',
  },
  {
    icon: GitBranch,
    title: 'Specialist agents, coordinated',
    description:
      'Research, Analysis, Critic, and Writer agents hand off work through a supervised pipeline you can watch run.',
  },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')

  function startResearch() {
    navigate('/dashboard')
  }

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <nav className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        <div className="hidden items-center gap-8 md:flex">
          <a href="#product" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Product
          </a>
          <a href="#workflow" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Workflow
          </a>
          <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Docs
          </a>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/dashboard">Sign in</Link>
          </Button>
          <Button size="sm" asChild>
            <Link to="/dashboard">
              Open workspace
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </nav>

      <section className="relative mx-auto flex max-w-3xl flex-col items-center px-6 pb-20 pt-16 text-center sm:pt-24">
        <div className="mb-6 inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/50 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="h-3 w-3 text-primary" />
          Multi-agent research operating system
        </div>

        <h1 className="text-balance text-4xl font-semibold leading-[1.1] tracking-tight text-foreground sm:text-6xl">
          Decisions backed by evidence, <span className="text-primary">not guesswork.</span>
        </h1>

        <p className="mt-5 max-w-xl text-balance text-base text-muted-foreground sm:text-lg">
          Evident runs a coordinated team of research agents against your hardest questions — and shows its
          work at every step.
        </p>

        <Card className="mt-10 w-full p-2 text-left shadow-glow">
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ask a research question — e.g. Should we enter the vertical SaaS healthcare market in 2027?"
            className="min-h-24 resize-none border-none bg-transparent px-3 py-3 text-sm shadow-none focus-visible:ring-0"
          />
          <div className="flex items-center justify-between gap-3 px-2 pb-1 pt-1">
            <span className="hidden text-xs text-muted-foreground sm:inline">
              Runs a full Supervisor → Research → Analysis → Critic → Writer pipeline
            </span>
            <Button size="sm" className="ml-auto gap-1.5" onClick={startResearch}>
              Start research
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </Card>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {examplePrompts.map((example) => (
            <button
              key={example}
              onClick={() => setPrompt(example)}
              className="rounded-full border border-border bg-card/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      <section id="workflow" className="relative mx-auto max-w-5xl px-6 pb-24">
        <Card className="overflow-hidden p-8 sm:p-10">
          <p className="text-center text-xs font-medium uppercase tracking-wider text-muted-foreground/70">
            How a research run works
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-between sm:gap-2">
            {PIPELINE.map((step, i) => (
              <div key={step} className="flex w-full items-center gap-2 sm:w-auto">
                <div className="flex flex-1 items-center gap-3 rounded-lg border border-border bg-secondary/40 px-4 py-3 sm:flex-none">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/15 text-xs font-semibold text-primary">
                    {i + 1}
                  </span>
                  <span className="text-sm font-medium text-foreground">{step}</span>
                </div>
                {i < PIPELINE.length - 1 && (
                  <ArrowRight className="hidden h-4 w-4 shrink-0 text-muted-foreground/40 sm:block" />
                )}
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section id="product" className="relative mx-auto max-w-6xl px-6 pb-28">
        <div className="grid gap-5 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} className="p-6">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent">
                <feature.icon className="h-4 w-4 text-accent-foreground" />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-foreground">{feature.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="relative mx-auto max-w-3xl px-6 pb-28 text-center">
        <Card className="flex flex-col items-center gap-4 p-10 shadow-glow">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">
            Bring evidence to your next decision.
          </h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Open the workspace and watch a research pipeline run end to end on a real question.
          </p>
          <Button size="lg" className="mt-2 gap-2" asChild>
            <Link to="/dashboard">
              Open workspace
              <ArrowUpRight className="h-4 w-4" />
            </Link>
          </Button>
        </Card>
      </section>

      <footer className="relative border-t border-border px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
          <Logo />
          <p className="text-xs text-muted-foreground">© 2026 Evident. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
