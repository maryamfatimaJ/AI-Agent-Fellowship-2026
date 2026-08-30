import type { ConversationDetail } from './api'

export function conversationToMarkdown(conversation: ConversationDetail): string {
  const title = conversation.title || 'Conversation'
  const lines = [`# ${title}`, '']

  for (const message of conversation.messages) {
    const speaker = message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Assistant' : message.role
    lines.push(`**${speaker}** _(${new Date(message.created_at).toLocaleString()})_`, '', message.content, '')

    if (message.citations && message.citations.length > 0) {
      lines.push('Sources:')
      for (const citation of message.citations) {
        lines.push(`- ${citation.filename} (chunk ${citation.chunk_index})`)
      }
      lines.push('')
    }
  }

  return lines.join('\n')
}

export function downloadConversationAsMarkdown(conversation: ConversationDetail): void {
  const markdown = conversationToMarkdown(conversation)
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const filename = (conversation.title || 'conversation').replace(/[^a-z0-9-_ ]/gi, '').trim() || 'conversation'
  link.href = url
  link.download = `${filename}.md`
  link.click()
  URL.revokeObjectURL(url)
}
