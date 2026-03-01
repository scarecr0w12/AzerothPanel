import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

interface PageMeta { title: string; subtitle: string }

const PAGE_META: Record<string, PageMeta> = {
  '/':                 { title: 'Dashboard',        subtitle: 'Real-time status overview of your AzerothCore server' },
  '/server':           { title: 'Server Control',   subtitle: 'Start, stop and restart server processes, and send GM commands' },
  '/logs':             { title: 'Logs',             subtitle: 'Live log streaming from worldserver, authserver and GM activity' },
  '/players':          { title: 'Players',          subtitle: 'View online characters, manage accounts and send announcements' },
  '/database':         { title: 'Database',         subtitle: 'Browse tables and run SQL queries against auth, characters and world DBs' },
  '/installation':     { title: 'Installation',     subtitle: 'Clone the AzerothCore repository and run the initial database setup' },
  '/compilation':      { title: 'Compilation',      subtitle: 'Build the server binaries with CMake and configure build flags' },
  '/data-extraction':  { title: 'Data Extraction',  subtitle: 'Extract or download client data (maps, VMaps, MMaps, DBC)' },
  '/modules':          { title: 'Modules',          subtitle: 'Browse and install AzerothCore modules from the catalogue' },
  '/configs':          { title: 'Config Files',     subtitle: 'Edit worldserver and authserver .conf files directly in the browser' },
  '/settings':         { title: 'Settings',         subtitle: 'Configure paths, database credentials and panel preferences' },
}

export default function Layout() {
  const { pathname } = useLocation()
  const meta = PAGE_META[pathname] ?? { title: 'AzerothPanel', subtitle: '' }

  return (
    <div className="flex h-screen overflow-hidden bg-panel-bg">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header title={meta.title} subtitle={meta.subtitle} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

