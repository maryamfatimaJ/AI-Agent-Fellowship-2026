import type { AgentStatus } from '@/components/status-badge'

export interface AgentNode {
  id: string
  name: string
  role: string
  status: AgentStatus
  progress: number
  detail: string
  startedAt?: string
  finishedAt?: string
  tokensUsed?: number
}

export const pipelineAgents: AgentNode[] = [
  {
    id: 'supervisor',
    name: 'Supervisor',
    role: 'Orchestration',
    status: 'completed',
    progress: 100,
    detail: 'Decomposed research question into 4 sub-tasks and routed to specialist agents.',
    startedAt: '09:41:02',
    finishedAt: '09:41:18',
    tokensUsed: 1180,
  },
  {
    id: 'research',
    name: 'Research',
    role: 'Source discovery',
    status: 'completed',
    progress: 100,
    detail: 'Gathered 34 candidate sources across 6 queries, filtered to 21 by relevance.',
    startedAt: '09:41:19',
    finishedAt: '09:44:52',
    tokensUsed: 8420,
  },
  {
    id: 'analysis',
    name: 'Analysis',
    role: 'Synthesis & reasoning',
    status: 'running',
    progress: 62,
    detail: 'Cross-referencing market sizing claims against 3 independent sources.',
    startedAt: '09:44:53',
    tokensUsed: 5310,
  },
  {
    id: 'critic',
    name: 'Critic',
    role: 'Adversarial verification',
    status: 'waiting',
    progress: 0,
    detail: 'Will stress-test analysis claims for unsupported inference and bias.',
  },
  {
    id: 'writer',
    name: 'Writer',
    role: 'Report generation',
    status: 'waiting',
    progress: 0,
    detail: 'Will compile the final decision brief with citations once critic signs off.',
  },
]

export interface TaskRow {
  id: string
  task: string
  agent: string
  priority: 'Low' | 'Medium' | 'High' | 'Critical'
  status: AgentStatus
  progress: number
}

export const tasks: TaskRow[] = [
  {
    id: 'T-1042',
    task: 'Identify top 5 competitors in the vertical SaaS space',
    agent: 'Research',
    priority: 'High',
    status: 'completed',
    progress: 100,
  },
  {
    id: 'T-1043',
    task: 'Validate TAM/SAM/SOM figures against 2 independent reports',
    agent: 'Analysis',
    priority: 'Critical',
    status: 'running',
    progress: 62,
  },
  {
    id: 'T-1044',
    task: 'Summarize regulatory risk for EU market entry',
    agent: 'Research',
    priority: 'Medium',
    status: 'completed',
    progress: 100,
  },
  {
    id: 'T-1045',
    task: 'Flag unsupported claims in pricing analysis',
    agent: 'Critic',
    priority: 'High',
    status: 'waiting',
    progress: 0,
  },
  {
    id: 'T-1046',
    task: 'Draft executive summary section',
    agent: 'Writer',
    priority: 'Medium',
    status: 'waiting',
    progress: 0,
  },
  {
    id: 'T-1047',
    task: 'Reconcile conflicting churn-rate benchmarks',
    agent: 'Analysis',
    priority: 'High',
    status: 'paused',
    progress: 34,
  },
  {
    id: 'T-1041',
    task: 'Scope research question and success criteria',
    agent: 'Supervisor',
    priority: 'Low',
    status: 'completed',
    progress: 100,
  },
  {
    id: 'T-1048',
    task: 'Cross-check customer quotes against source transcripts',
    agent: 'Critic',
    priority: 'Critical',
    status: 'failed',
    progress: 45,
  },
]

export interface EvidenceItem {
  id: string
  claim: string
  source: string
  sourceUrl: string
  confidence: number
  agent: string
  excerpt: string
  collectedAt: string
  tags: string[]
}

export const evidenceItems: EvidenceItem[] = [
  {
    id: 'E-201',
    claim: 'Vertical SaaS market is projected to grow at 19.4% CAGR through 2029',
    source: 'Gartner Market Forecast, 2025',
    sourceUrl: 'gartner.com/research/vertical-saas-2025',
    confidence: 92,
    agent: 'Research',
    excerpt:
      '"...vertical SaaS spend across healthcare, logistics, and legal is expected to outpace horizontal platforms, driven by workflow-native AI features..."',
    collectedAt: '2 hours ago',
    tags: ['market-sizing', 'high-confidence'],
  },
  {
    id: 'E-202',
    claim: 'Average enterprise contract value increased 23% YoY for AI-native tools',
    source: 'OpenView 2025 SaaS Benchmarks Report',
    sourceUrl: 'openviewpartners.com/2025-benchmarks',
    confidence: 81,
    agent: 'Analysis',
    excerpt:
      '"...ACV growth was most pronounced among tools shipping agentic features, with median expansion revenue up 23% year-over-year..."',
    collectedAt: '3 hours ago',
    tags: ['pricing', 'benchmarks'],
  },
  {
    id: 'E-203',
    claim: 'Three of five reviewed competitors lack SOC 2 Type II certification',
    source: 'Vendor trust center audit (manual review)',
    sourceUrl: 'internal/vendor-trust-audit',
    confidence: 74,
    agent: 'Research',
    excerpt: '"Trust center pages for Competitor B, D, and E show SOC 2 Type I only, last audited over 14 months ago."',
    collectedAt: '4 hours ago',
    tags: ['compliance', 'risk'],
  },
  {
    id: 'E-204',
    claim: 'Churn benchmark of 4.1% monthly cited by two sources conflicts with a third reporting 6.8%',
    source: 'ChartMogul vs. ProfitWell vs. internal cohort data',
    sourceUrl: 'chartmogul.com/saas-benchmarks',
    confidence: 48,
    agent: 'Critic',
    excerpt: '"Segment definitions differ across reports — ProfitWell includes downgrade churn, ChartMogul does not."',
    collectedAt: '38 minutes ago',
    tags: ['needs-review', 'churn'],
  },
  {
    id: 'E-205',
    claim: 'GDPR enforcement actions against AI vendors rose 3x in the past 18 months',
    source: 'European Data Protection Board, 2025 enforcement bulletin',
    sourceUrl: 'edpb.europa.eu/bulletins/2025',
    confidence: 88,
    agent: 'Research',
    excerpt: '"...18 formal actions recorded against AI-feature vendors between Q1 2024 and Q2 2025, up from 6 in the prior period."',
    collectedAt: '5 hours ago',
    tags: ['regulatory', 'high-confidence'],
  },
]

export type LogLevel = 'info' | 'warning' | 'error' | 'tool'

export interface LogEntry {
  id: string
  time: string
  agent: string
  level: LogLevel
  message: string
  meta?: string
}

export const logEntries: LogEntry[] = [
  { id: 'L-01', time: '09:41:02', agent: 'Supervisor', level: 'info', message: 'Research session initialized', meta: 'session_id: rs_8f21ac' },
  { id: 'L-02', time: '09:41:04', agent: 'Supervisor', level: 'info', message: 'Decomposed goal into 4 sub-tasks' },
  { id: 'L-03', time: '09:41:19', agent: 'Research', level: 'tool', message: 'Called web_search', meta: 'query: "vertical SaaS market size 2025"' },
  { id: 'L-04', time: '09:42:07', agent: 'Research', level: 'tool', message: 'Called fetch_url', meta: 'gartner.com/research/vertical-saas-2025' },
  { id: 'L-05', time: '09:43:12', agent: 'Research', level: 'warning', message: 'Source behind soft paywall, using cached snapshot' },
  { id: 'L-06', time: '09:44:52', agent: 'Research', level: 'info', message: 'Completed source discovery — 21 sources retained' },
  { id: 'L-07', time: '09:44:53', agent: 'Analysis', level: 'info', message: 'Started cross-referencing market sizing claims' },
  { id: 'L-08', time: '09:46:31', agent: 'Analysis', level: 'tool', message: 'Called compare_sources', meta: 'sources: [E-201, E-202]' },
  { id: 'L-09', time: '09:48:02', agent: 'Analysis', level: 'error', message: 'Rate limited by data provider, retrying with backoff', meta: 'retry 1/3' },
  { id: 'L-10', time: '09:48:19', agent: 'Analysis', level: 'info', message: 'Retry succeeded' },
  { id: 'L-11', time: '09:49:40', agent: 'Analysis', level: 'warning', message: 'Conflicting churn benchmarks detected — flagged for Critic' },
]

export interface ProjectSummary {
  id: string
  title: string
  question: string
  status: AgentStatus
  progress: number
  updatedAt: string
  agentsRunning: number
  evidenceCount: number
}

export const projects: ProjectSummary[] = [
  {
    id: 'P-01',
    title: 'Vertical SaaS market entry',
    question: 'Should we enter the vertical SaaS market for healthcare scheduling in Q1 2027?',
    status: 'running',
    progress: 58,
    updatedAt: '2 minutes ago',
    agentsRunning: 1,
    evidenceCount: 21,
  },
  {
    id: 'P-02',
    title: 'Competitor pricing teardown',
    question: 'How does our pricing compare to the top 6 competitors across enterprise tiers?',
    status: 'completed',
    progress: 100,
    updatedAt: '1 day ago',
    agentsRunning: 0,
    evidenceCount: 34,
  },
  {
    id: 'P-03',
    title: 'EU regulatory exposure review',
    question: 'What is our compliance exposure if we launch AI features in the EU this year?',
    status: 'paused',
    progress: 41,
    updatedAt: '3 days ago',
    agentsRunning: 0,
    evidenceCount: 12,
  },
  {
    id: 'P-04',
    title: 'Churn driver investigation',
    question: 'What are the leading indicators behind the Q2 churn increase in mid-market accounts?',
    status: 'failed',
    progress: 27,
    updatedAt: '5 days ago',
    agentsRunning: 0,
    evidenceCount: 8,
  },
]

export const examplePrompts: string[] = [
  'Should we expand into the vertical SaaS healthcare market in 2027?',
  'What is the real risk of EU regulatory action against our AI roadmap?',
  'Is our enterprise pricing competitive against the top 5 alternatives?',
  'What is driving the churn increase in mid-market accounts this quarter?',
]

export const reportMarkdown = `# Vertical SaaS Market Entry — Decision Brief

**Prepared by:** Evident Research Pipeline · **Confidence:** High (84/100)

## Executive Summary

Entering the vertical SaaS healthcare scheduling market in Q1 2027 is **favorable**, contingent on closing the compliance gap identified in Section 3. Market growth, willingness-to-pay signals, and competitive white space all support entry; the primary risk is regulatory timing in EU markets.

## 1. Market Opportunity

The vertical SaaS market is projected to grow at a **19.4% CAGR through 2029** [E-201], substantially outpacing horizontal platform growth. Enterprise contract values for AI-native tools rose **23% year-over-year** [E-202], suggesting durable willingness-to-pay for workflow-embedded AI.

## 2. Competitive Landscape

Of five reviewed competitors, three lack current SOC 2 Type II certification [E-203], representing a meaningful trust gap we can close at entry. No competitor currently offers agentic scheduling assistance as a first-class feature.

## 3. Risk Factors

> **Flagged by Critic agent:** Churn benchmarks cited across sources conflict — 4.1% monthly (ChartMogul, ProfitWell) vs. 6.8% (internal cohort) [E-204]. Segment definitions differ; this should be reconciled before using churn as a planning input.

GDPR enforcement actions against AI vendors have **tripled in the past 18 months** [E-205]. Any EU rollout should budget 4-6 additional weeks for compliance review.

## 4. Recommendation

Proceed with entry, gated on:

1. Closing the SOC 2 Type II gap before GA
2. Reconciling churn methodology with Finance before using it in the business case
3. Sequencing EU launch 6 weeks behind US launch to absorb compliance review

---
*This report was generated by a multi-agent research pipeline. All claims are traceable to evidence items in the Evidence tab.*
`
