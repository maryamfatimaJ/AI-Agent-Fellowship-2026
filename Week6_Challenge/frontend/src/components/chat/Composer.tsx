import { useState, type KeyboardEvent, type ReactNode } from 'react'

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSend: (content: string) => Promise<void>
  disabled?: boolean
  toolbar?: ReactNode
}

export function Composer({ value, onChange, onSend, disabled, toolbar }: ComposerProps) {
  const [isSending, setIsSending] = useState(false)

  async function submit() {
    const content = value.trim()
    if (!content || isSending) return
    setIsSending(true)
    onChange('')
    try {
      await onSend(content)
    } finally {
      setIsSending(false)
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-line p-4">
      {toolbar && <div className="mb-2 flex items-center gap-2">{toolbar}</div>}
      <div className="flex items-end gap-2 rounded-lg border border-line bg-surface px-3 py-2 focus-within:border-accent">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || isSending}
          placeholder="Message your assistant… (Enter to send, Shift+Enter for a new line)"
          aria-label="Message"
          rows={1}
          className="max-h-40 flex-1 resize-none bg-transparent py-1 text-sm text-ink placeholder:text-ink-faint focus:outline-none"
        />
        <button
          onClick={submit}
          disabled={disabled || isSending || !value.trim()}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          {isSending ? 'Sending…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
