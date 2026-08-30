import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type Skill } from '../../lib/api'
import { EmptyState } from '../../components/EmptyState'

export function SkillsPage() {
  const { workspaceId = '' } = useParams()
  const navigate = useNavigate()
  const [skills, setSkills] = useState<Skill[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeSkill, setActiveSkill] = useState<Skill | null>(null)
  const [input, setInput] = useState('')
  const [output, setOutput] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  useEffect(() => {
    api
      .listSkills(workspaceId)
      .then(setSkills)
      .finally(() => setIsLoading(false))
  }, [workspaceId])

  async function handleRun() {
    if (!activeSkill || !input.trim()) return
    setIsRunning(true)
    setOutput(null)
    try {
      const result = await api.runSkill(workspaceId, activeSkill.id, input.trim())
      setOutput(result.output)
    } finally {
      setIsRunning(false)
    }
  }

  async function handleRunInNewChat() {
    if (!activeSkill || !input.trim()) return
    setIsRunning(true)
    try {
      const conversation = await api.createConversation(workspaceId)
      await api.runSkill(workspaceId, activeSkill.id, input.trim(), conversation.id)
      navigate(`/workspaces/${workspaceId}/c/${conversation.id}`)
    } finally {
      setIsRunning(false)
    }
  }

  const grouped = skills.reduce<Record<string, Skill[]>>((acc, skill) => {
    acc[skill.category] = acc[skill.category] ?? []
    acc[skill.category].push(skill)
    return acc
  }, {})

  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto px-6 py-10">
      <div className="mb-6 space-y-1">
        <h1 className="text-lg font-medium text-ink">Skills</h1>
        <p className="text-sm text-ink-muted">
          Reusable AI actions. Run one here, or reach for the same skills from any chat's composer.
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : skills.length === 0 ? (
        <EmptyState title="No skills available" />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-4">
            {Object.entries(grouped).map(([category, categorySkills]) => (
              <div key={category}>
                <h2 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-faint">{category}</h2>
                <ul className="space-y-1.5">
                  {categorySkills.map((skill) => (
                    <li key={skill.id}>
                      <button
                        onClick={() => {
                          setActiveSkill(skill)
                          setOutput(null)
                        }}
                        className={`block w-full rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
                          activeSkill?.id === skill.id
                            ? 'border-accent bg-accent-soft'
                            : 'border-line bg-surface hover:border-accent'
                        }`}
                      >
                        <p className="text-sm font-medium text-ink">{skill.name}</p>
                        {skill.description && <p className="text-xs text-ink-muted">{skill.description}</p>}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-line bg-surface p-4">
            {!activeSkill ? (
              <EmptyState title="Pick a skill" description="Select a skill on the left to run it." />
            ) : (
              <div className="space-y-3">
                <p className="font-medium text-ink">{activeSkill.name}</p>
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Paste or type the input for this skill…"
                  rows={6}
                  className="w-full resize-none rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleRun}
                    disabled={isRunning || !input.trim()}
                    className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                  >
                    {isRunning ? 'Running…' : 'Run'}
                  </button>
                  <button
                    onClick={handleRunInNewChat}
                    disabled={isRunning || !input.trim()}
                    className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-accent disabled:opacity-50"
                  >
                    Run in new chat
                  </button>
                </div>
                {output && (
                  <div className="whitespace-pre-wrap rounded-md border border-line-soft bg-canvas px-3 py-2.5 text-sm text-ink">
                    {output}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
