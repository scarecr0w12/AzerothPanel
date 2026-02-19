import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Loader2 } from 'lucide-react'
import { authApi } from '@/services/api'
import { useAuthStore } from '@/store'

export default function Login() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await authApi.login(username, password)
      setAuth(data.access_token, username)
      navigate('/')
    } catch {
      setError('Invalid username or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-panel-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="p-3 bg-brand/15 rounded-2xl mb-4">
            <Shield size={36} className="text-brand" />
          </div>
          <h1 className="text-2xl font-bold text-white">AzerothPanel</h1>
          <p className="text-sm text-panel-muted mt-1">Sign in to manage your server</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-panel-surface border border-panel-border rounded-2xl p-6 space-y-4"
        >
          {error && (
            <div className="bg-danger/10 border border-danger/30 text-danger text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-panel-muted uppercase tracking-wide">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2.5
                         text-white text-sm placeholder-panel-muted
                         focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand/30"
              placeholder="admin"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-panel-muted uppercase tracking-wide">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="w-full bg-panel-bg border border-panel-border rounded-lg px-3 py-2.5
                         text-white text-sm placeholder-panel-muted
                         focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand/30"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand hover:bg-brand-hover disabled:opacity-50
                       text-white font-semibold py-2.5 rounded-lg transition-colors
                       flex items-center justify-center gap-2"
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}

