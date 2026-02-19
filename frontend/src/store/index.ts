import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  username: string | null
  setAuth: (token: string, username: string) => void
  clearAuth: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      username: null,
      setAuth: (token, username) => {
        localStorage.setItem('ap_token', token)
        set({ token, username })
      },
      clearAuth: () => {
        localStorage.removeItem('ap_token')
        set({ token: null, username: null })
      },
      isAuthenticated: () => !!get().token,
    }),
    { name: 'ap-auth' }
  )
)

// ─── UI State ─────────────────────────────────────────────────────────────────
interface UIState {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}))

