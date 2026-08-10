import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { TooltipProvider } from '@/components/ui/tooltip'
import { AppShell } from '@/components/layout/app-shell'
import LandingPage from '@/pages/landing'
import DashboardPage from '@/pages/dashboard'
import WorkflowPage from '@/pages/workflow'
import TasksPage from '@/pages/tasks'
import EvidencePage from '@/pages/evidence'
import LogsPage from '@/pages/logs'
import ReportsPage from '@/pages/reports'

function App() {
  return (
    <TooltipProvider delayDuration={150}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/workflow" element={<WorkflowPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/evidence" element={<EvidencePage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  )
}

export default App
