import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { AuthProvider } from './lib/AuthContext'
import { ThemeProvider } from './lib/ThemeContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppShell } from './components/AppShell'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { WorkspacesPage } from './pages/WorkspacesPage'
import { WorkspaceShell } from './pages/workspace/WorkspaceShell'
import { DashboardPage } from './pages/workspace/DashboardPage'
import { ChatPage } from './pages/workspace/ChatPage'
import { AssistantPage } from './pages/workspace/AssistantPage'
import { DocumentsPage } from './pages/workspace/DocumentsPage'
import { MemoryPage } from './pages/workspace/MemoryPage'
import { PromptsPage } from './pages/workspace/PromptsPage'
import { SkillsPage } from './pages/workspace/SkillsPage'
import { QualityDashboardPage } from './pages/workspace/QualityDashboardPage'
import { TraceViewerPage } from './pages/workspace/TraceViewerPage'
import { GuardrailsPage } from './pages/workspace/GuardrailsPage'

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppShell />}>
                <Route path="/workspaces" element={<WorkspacesPage />} />
              </Route>
              <Route path="/workspaces/:workspaceId" element={<WorkspaceShell />}>
                <Route index element={<DashboardPage />} />
                <Route path="c/:conversationId" element={<ChatPage />} />
                <Route path="assistant" element={<AssistantPage />} />
                <Route path="knowledge" element={<DocumentsPage />} />
                <Route path="memory" element={<MemoryPage />} />
                <Route path="prompts" element={<PromptsPage />} />
                <Route path="skills" element={<SkillsPage />} />
                <Route path="quality-dashboard" element={<QualityDashboardPage />} />
                <Route path="traces" element={<TraceViewerPage />} />
                <Route path="guardrails" element={<GuardrailsPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/workspaces" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
