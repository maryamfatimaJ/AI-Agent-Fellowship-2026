import type { Message } from '../../lib/api'

interface MessageBubbleProps {
  message: Message
  onTogglePin?: (message: Message) => void
}

export function MessageBubble({ message, onTogglePin }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isPersisted = !message.id.startsWith('pending-')

  return (
    <div className={`group flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[70ch] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1.5`}>
        <div className="flex items-start gap-1.5">
          {!isUser && onTogglePin && isPersisted && (
            <button
              onClick={() => onTogglePin(message)}
              aria-label={message.pinned ? 'Unpin message' : 'Pin message'}
              title={message.pinned ? 'Unpin message' : 'Pin message'}
              className={`mt-1 text-xs opacity-0 transition-opacity group-hover:opacity-100 ${
                message.pinned ? 'text-accent opacity-100' : 'text-ink-faint hover:text-accent'
              }`}
            >
              {message.pinned ? '★' : '☆'}
            </button>
          )}
          <div
            className={`whitespace-pre-wrap rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
              isUser ? 'bg-accent text-white' : 'border border-line bg-surface text-ink'
            }`}
          >
            {message.content}
          </div>
          {isUser && onTogglePin && isPersisted && (
            <button
              onClick={() => onTogglePin(message)}
              aria-label={message.pinned ? 'Unpin message' : 'Pin message'}
              title={message.pinned ? 'Unpin message' : 'Pin message'}
              className={`mt-1 text-xs opacity-0 transition-opacity group-hover:opacity-100 ${
                message.pinned ? 'text-accent opacity-100' : 'text-ink-faint hover:text-accent'
              }`}
            >
              {message.pinned ? '★' : '☆'}
            </button>
          )}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.citations.map((citation, index) => (
              <span
                key={`${citation.document_id}-${citation.chunk_index}-${index}`}
                title={citation.snippet}
                className="cursor-help rounded-full border border-line-soft bg-surface px-2.5 py-1 text-xs text-ink-muted"
              >
                {citation.filename} · chunk {citation.chunk_index}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
