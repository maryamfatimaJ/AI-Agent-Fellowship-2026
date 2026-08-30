import { useCallback, useEffect, useState } from 'react'
import { api, type PromptTemplate } from '../../lib/api'
import { useClickOutside } from '../../lib/useClickOutside'

export function PromptPicker({ workspaceId, onPick }: { workspaceId: string; onPick: (content: string) => void }) {
  const [isOpen, setIsOpen] = useState(false)
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const ref = useClickOutside<HTMLDivElement>(useCallback(() => setIsOpen(false), []))

  useEffect(() => {
    if (isOpen) api.listPrompts(workspaceId).then(setPrompts)
  }, [isOpen, workspaceId])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="rounded-md border border-line px-2.5 py-1 text-xs text-ink-muted hover:border-accent hover:text-accent"
      >
        Prompts
      </button>
      {isOpen && (
        <div className="absolute bottom-full left-0 z-10 mb-1.5 max-h-72 w-72 overflow-y-auto rounded-lg border border-line bg-surface p-1.5 shadow-lg">
          {prompts.length === 0 ? (
            <p className="px-2 py-3 text-center text-xs text-ink-muted">No prompts yet.</p>
          ) : (
            prompts.map((prompt) => (
              <button
                key={prompt.id}
                onClick={() => {
                  onPick(prompt.content)
                  setIsOpen(false)
                }}
                className="block w-full rounded-md px-2.5 py-2 text-left hover:bg-line-soft"
              >
                <p className="text-sm text-ink">{prompt.name}</p>
                <p className="truncate text-xs text-ink-muted">{prompt.content}</p>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
