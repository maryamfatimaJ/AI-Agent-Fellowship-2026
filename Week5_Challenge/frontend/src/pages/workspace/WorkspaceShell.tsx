import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { api, type Conversation, type Workspace } from '../../lib/api'
import { useAuth } from '../../lib/AuthContext'
import { ThemeToggle } from '../../components/ThemeToggle'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-md px-2.5 py-1.5 text-sm ${
    isActive ? 'bg-accent-soft text-ink' : 'text-ink-muted hover:bg-line-soft hover:text-ink'
  }`

export function WorkspaceShell() {
  const { workspaceId = '' } = useParams()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  async function refreshConversations(query?: string) {
    const list = await api.listConversations(workspaceId, query)
    setConversations(list)
  }

  useEffect(() => {
    setIsLoading(true)
    Promise.all([api.getWorkspace(workspaceId), api.listConversations(workspaceId)])
      .then(([ws, convos]) => {
        setWorkspace(ws)
        setConversations(convos)
      })
      .finally(() => setIsLoading(false))
  }, [workspaceId])

  useEffect(() => {
    const timeout = setTimeout(() => {
      refreshConversations(search || undefined)
    }, 250)
    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  async function handleNewChat() {
    const conversation = await api.createConversation(workspaceId)
    setConversations((prev) => [conversation, ...prev])
    setIsSidebarOpen(false)
    navigate(`/workspaces/${workspaceId}/c/${conversation.id}`)
  }

  return (
    <div className="flex h-screen bg-canvas">
      {isSidebarOpen && (
        <div
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 z-10 bg-black/20 md:hidden"
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-20 flex w-64 flex-shrink-0 flex-col border-r border-line bg-canvas transition-transform md:relative md:translate-x-0 ${
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="border-b border-line p-4">
          <NavLink to="/workspaces" className="text-xs text-ink-muted hover:text-ink">
            &larr; All workspaces
          </NavLink>
          <p className="mt-1 truncate text-sm font-medium text-ink">
            {isLoading ? 'Loading…' : workspace?.name}
          </p>
        </div>

        <div className="space-y-0.5 border-b border-line p-2">
          <NavLink to={`/workspaces/${workspaceId}`} end className={navLinkClass} onClick={() => setIsSidebarOpen(false)}>
            Dashboard
          </NavLink>
          <NavLink to={`/workspaces/${workspaceId}/prompts`} className={navLinkClass} onClick={() => setIsSidebarOpen(false)}>
            Prompts
          </NavLink>
          <NavLink to={`/workspaces/${workspaceId}/skills`} className={navLinkClass} onClick={() => setIsSidebarOpen(false)}>
            Skills
          </NavLink>
          <NavLink to={`/workspaces/${workspaceId}/assistant`} className={navLinkClass} onClick={() => setIsSidebarOpen(false)}>
            Assistant
          </NavLink>
          <NavLink to={`/workspaces/${workspaceId}/knowledge`} className={navLinkClass} onClick={() => setIsSidebarOpen(false)}>
            Knowledge base
          </NavLink>
          <NavLink to={`/workspaces/${workspaceId}/memory`} className={navLinkClass} onClick={() => setIsSidebarOpen(false)}>
            Memory
          </NavLink>
        </div>

        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="w-full rounded-md border border-line px-3 py-2 text-left text-sm text-ink transition-colors hover:border-accent hover:text-accent"
          >
            + New chat
          </button>
        </div>

        <div className="px-3 pb-2">
          <label htmlFor="conversation-search" className="sr-only">
            Search conversations
          </label>
          <input
            id="conversation-search"
            type="text"
            placeholder="Search conversations"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
        </div>

        <nav aria-label="Conversations" className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
          {conversations.map((conversation) => (
            <NavLink
              key={conversation.id}
              to={`/workspaces/${workspaceId}/c/${conversation.id}`}
              onClick={() => setIsSidebarOpen(false)}
              className={({ isActive }) =>
                `block truncate rounded-md px-2.5 py-1.5 text-sm ${
                  isActive ? 'bg-accent-soft text-ink' : 'text-ink-muted hover:bg-line-soft hover:text-ink'
                }`
              }
            >
              {conversation.title || 'New conversation'}
            </NavLink>
          ))}
          {!isLoading && conversations.length === 0 && (
            <p className="px-2.5 py-2 text-sm text-ink-faint">No conversations yet.</p>
          )}
        </nav>

        <div className="space-y-2 border-t border-line p-3">
          <div className="flex items-center justify-between">
            <span className="truncate text-xs text-ink-muted">{user?.email}</span>
            <button onClick={logout} className="text-xs text-ink-muted hover:text-ink">
              Log out
            </button>
          </div>
          <ThemeToggle />
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center border-b border-line px-3 py-2 md:hidden">
          <button
            onClick={() => setIsSidebarOpen(true)}
            aria-label="Open sidebar"
            className="rounded-md border border-line px-2.5 py-1 text-sm text-ink-muted"
          >
            ☰
          </button>
        </div>
        <main className="flex-1 overflow-hidden">
          <Outlet context={{ workspace, refreshConversations }} />
        </main>
      </div>
    </div>
  )
}
