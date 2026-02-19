import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

const PAGE_TITLES: Record<string, string> = {
  '/':             'Dashboard',
  '/server':       'Server Control',
  '/logs':         'Log Viewer',
  '/players':      'Player Management',
  '/database':     'Database Manager',
  '/compilation':  'Compilation',
  '/installation': 'Installation & Setup',
}

export default function Layout() {
  const { pathname } = useLocation()
  const title = PAGE_TITLES[pathname] ?? 'AzerothPanel'

  return (
    <div className="flex h-screen overflow-hidden bg-panel-bg">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header title={title} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

