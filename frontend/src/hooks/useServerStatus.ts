import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { serverApi } from '@/services/api'
import { toast } from '@/components/ui/Toast'
import type { ServerStatus, ServerActionResponse } from '@/types'

export function useServerStatus(refetchInterval = 5000) {
  return useQuery<ServerStatus>({
    queryKey: ['server-status'],
    queryFn: () => serverApi.status().then((r) => r.data),
    refetchInterval,
    retry: false,
  })
}

function useServerAction(
  fn: () => Promise<{ data: ServerActionResponse }>,
  actionName: string
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (response) => {
      // Show toast notification
      if (response.data.success) {
        toast(response.data.message || `${actionName} successful`, 'success')
      } else {
        toast(response.data.message || `${actionName} failed`, 'error')
      }
      // Refresh status after any action
      setTimeout(() => qc.invalidateQueries({ queryKey: ['server-status'] }), 1500)
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      const message = err.response?.data?.detail || `${actionName} failed`
      toast(message, 'error')
      // Still refresh status
      setTimeout(() => qc.invalidateQueries({ queryKey: ['server-status'] }), 1500)
    },
  })
}

export function useStartWorld() {
  return useServerAction(serverApi.startWorld, 'Start worldserver')
}
export function useStopWorld() {
  return useServerAction(serverApi.stopWorld, 'Stop worldserver')
}
export function useRestartWorld() {
  return useServerAction(serverApi.restartWorld, 'Restart worldserver')
}
export function useStartAuth() {
  return useServerAction(serverApi.startAuth, 'Start authserver')
}
export function useStopAuth() {
  return useServerAction(serverApi.stopAuth, 'Stop authserver')
}
export function useRestartAuth() {
  return useServerAction(serverApi.restartAuth, 'Restart authserver')
}

