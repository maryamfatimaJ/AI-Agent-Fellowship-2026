import { useEffect, useRef, useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'
import { api, type ConversationDetail, type Message, type Skill } from '../../lib/api'
import { MessageBubble } from '../../components/chat/MessageBubble'
import { Composer } from '../../components/chat/Composer'
import { PromptPicker } from '../../components/chat/PromptPicker'
import { SkillPicker } from '../../components/chat/SkillPicker'
import { EmptyState } from '../../components/EmptyState'
import { downloadConversationAsMarkdown } from '../../lib/exportConversation'

interface WorkspaceOutletContext {
  refreshConversations: (query?: string) => Promise<void>
}

export function ChatPage() {
  const { workspaceId = '', conversationId = '' } = useParams()
  const { refreshConversations } = useOutletContext<WorkspaceOutletContext>()

  const [conversation, setConversation] = useState<ConversationDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [showPinned, setShowPinned] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setIsLoading(true)
    setError(null)
    setDraft('')
    setShowPinned(false)
    api
      .getConversation(workspaceId, conversationId)
      .then(setConversation)
      .catch(() => setError('Could not load this conversation.'))
      .finally(() => setIsLoading(false))
  }, [workspaceId, conversationId])

  useEffect(() => {
    if (!showPinned) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [conversation?.messages.length, showPinned])

  async function handleSend(content: string) {
    if (!conversation) return
    setError(null)
    const placeholder: Message = {
      id: `pending-${Date.now()}`,
      conversation_id: conversation.id,
      role: 'user',
      content,
      citations: null,
      pinned: false,
      created_at: new Date().toISOString(),
    }
    setConversation((prev) => (prev ? { ...prev, messages: [...prev.messages, placeholder] } : prev))
    setIsSending(true)

    try {
      const { user_message, assistant_message } = await api.sendMessage(workspaceId, conversationId, content)
      setConversation((prev) =>
        prev
          ? {
              ...prev,
              messages: [...prev.messages.filter((m) => m.id !== placeholder.id), user_message, assistant_message],
            }
          : prev
      )
      refreshConversations()
    } catch {
      setError('The assistant could not respond. Please try again.')
      setConversation((prev) => (prev ? { ...prev, messages: prev.messages.filter((m) => m.id !== placeholder.id) } : prev))
    } finally {
      setIsSending(false)
    }
  }

  async function handleRunSkill(skill: Skill) {
    if (!conversation || !draft.trim()) return
    setError(null)
    setIsSending(true)
    const input = draft
    setDraft('')
    try {
      const { user_message, assistant_message } = await api.runSkill(workspaceId, skill.id, input, conversationId)
      setConversation((prev) =>
        prev && user_message && assistant_message
          ? { ...prev, messages: [...prev.messages, user_message, assistant_message] }
          : prev
      )
      refreshConversations()
    } catch {
      setError(`Could not run "${skill.name}". Please try again.`)
    } finally {
      setIsSending(false)
    }
  }

  async function handleTogglePin(message: Message) {
    const updated = await api.setMessagePinned(workspaceId, conversationId, message.id, !message.pinned)
    setConversation((prev) =>
      prev ? { ...prev, messages: prev.messages.map((m) => (m.id === updated.id ? updated : m)) } : prev
    )
  }

  if (isLoading) {
    return <EmptyState title="Loading conversation…" />
  }

  if (!conversation) {
    return <EmptyState title="Conversation not found" description="It may have been deleted." />
  }

  const pinnedMessages = conversation.messages.filter((m) => m.pinned)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-line px-6 py-2.5">
        <button
          onClick={() => setShowPinned((prev) => !prev)}
          className={`text-xs ${pinnedMessages.length > 0 ? 'text-ink-muted hover:text-ink' : 'text-ink-faint'}`}
          disabled={pinnedMessages.length === 0}
        >
          {showPinned ? '← Back to conversation' : `★ Pinned (${pinnedMessages.length})`}
        </button>
        <button
          onClick={() => downloadConversationAsMarkdown(conversation)}
          className="text-xs text-ink-muted hover:text-ink"
        >
          Export as Markdown
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {showPinned ? (
          pinnedMessages.length === 0 ? (
            <EmptyState title="No pinned messages" />
          ) : (
            pinnedMessages.map((message) => (
              <MessageBubble key={message.id} message={message} onTogglePin={handleTogglePin} />
            ))
          )
        ) : conversation.messages.length === 0 ? (
          <EmptyState
            title="Start the conversation"
            description="Ask a question, brainstorm, or reference a document from the workspace's knowledge base."
          />
        ) : (
          conversation.messages.map((message) => (
            <MessageBubble key={message.id} message={message} onTogglePin={handleTogglePin} />
          ))
        )}
        {isSending && (
          <div className="flex justify-start">
            <div className="rounded-lg border border-line bg-surface px-4 py-2.5 text-sm text-ink-muted">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {error && <p className="px-6 pb-2 text-sm text-danger">{error}</p>}

      <Composer
        value={draft}
        onChange={setDraft}
        onSend={handleSend}
        disabled={isSending}
        toolbar={
          <>
            <PromptPicker workspaceId={workspaceId} onPick={(content) => setDraft(content)} />
            <SkillPicker workspaceId={workspaceId} onPick={handleRunSkill} />
          </>
        }
      />
    </div>
  )
}
