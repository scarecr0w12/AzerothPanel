import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/store'
import type { ReactNode } from 'react'

import Layout from '@/components/layout/Layout'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import ServerControl from '@/pages/ServerControl'
import LogViewer from '@/pages/LogViewer'
import PlayerManagement from '@/pages/PlayerManagement'
import DatabaseManager from '@/pages/DatabaseManager'
import Compilation from '@/pages/Compilation'
import Installation from '@/pages/Installation'
import Settings from '@/pages/Settings'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="server" element={<ServerControl />} />
        <Route path="logs" element={<LogViewer />} />
        <Route path="players" element={<PlayerManagement />} />
        <Route path="database" element={<DatabaseManager />} />
        <Route path="compilation" element={<Compilation />} />
        <Route path="installation" element={<Installation />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      {/* Catch-all → dashboard */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

