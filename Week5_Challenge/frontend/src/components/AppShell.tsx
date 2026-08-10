import { Outlet } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import { ThemeToggle } from './ThemeToggle'

export function AppShell() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="flex items-center justify-between border-b border-line px-6 py-3.5">
        <span className="text-sm font-medium text-ink">AI Workspace Platform</span>
        <div className="flex items-center gap-4 text-sm text-ink-muted">
          <ThemeToggle />
          <span>{user?.email}</span>
          <button onClick={logout} className="text-ink-muted hover:text-ink">
            Log out
          </button>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}
