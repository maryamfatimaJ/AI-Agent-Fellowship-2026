import { Outlet } from 'react-router-dom'

import { Sidebar } from '@/components/layout/sidebar'
import { Navbar } from '@/components/layout/navbar'

export function AppShell() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="lg:pl-60">
        <Navbar />
        <main className="mx-auto max-w-[1400px] px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
