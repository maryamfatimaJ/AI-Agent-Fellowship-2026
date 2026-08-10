import { useCallback, useEffect, useState } from 'react'
import { api, type Skill } from '../../lib/api'
import { useClickOutside } from '../../lib/useClickOutside'

export function SkillPicker({ workspaceId, onPick }: { workspaceId: string; onPick: (skill: Skill) => void }) {
  const [isOpen, setIsOpen] = useState(false)
  const [skills, setSkills] = useState<Skill[]>([])
  const ref = useClickOutside<HTMLDivElement>(useCallback(() => setIsOpen(false), []))

  useEffect(() => {
    if (isOpen) api.listSkills(workspaceId).then(setSkills)
  }, [isOpen, workspaceId])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="rounded-md border border-line px-2.5 py-1 text-xs text-ink-muted hover:border-accent hover:text-accent"
      >
        Run a skill
      </button>
      {isOpen && (
        <div className="absolute bottom-full left-0 z-10 mb-1.5 max-h-72 w-72 overflow-y-auto rounded-lg border border-line bg-surface p-1.5 shadow-lg">
          {skills.map((skill) => (
            <button
              key={skill.id}
              onClick={() => {
                onPick(skill)
                setIsOpen(false)
              }}
              className="block w-full rounded-md px-2.5 py-2 text-left hover:bg-line-soft"
            >
              <p className="text-sm text-ink">{skill.name}</p>
              {skill.description && <p className="truncate text-xs text-ink-muted">{skill.description}</p>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
