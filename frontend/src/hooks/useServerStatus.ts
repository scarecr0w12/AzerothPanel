import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { serverApi } from '@/services/api'
import type { ServerStatus, ServerActionResponse } from '@/types'

export function useServerStatus(refetchInterval = 5000) {
  return useQuery<ServerStatus>({
    queryKey: ['server-status'],
    queryFn: () => serverApi.status().then((r) => r.data),
    refetchInterval,
    retry: false,
  })
}

function useServerAction(fn: () => Promise<{ data: ServerActionResponse }>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSettled: () => {
      // Refresh status after any action
      setTimeout(() => qc.invalidateQueries({ queryKey: ['server-status'] }), 1500)
    },
  })
}

export function useStartWorld() {
  return useServerAction(serverApi.startWorld)
}
export function useStopWorld() {
  return useServerAction(serverApi.stopWorld)
}
export function useRestartWorld() {
  return useServerAction(serverApi.restartWorld)
}
export function useStartAuth() {
  return useServerAction(serverApi.startAuth)
}
export function useStopAuth() {
  return useServerAction(serverApi.stopAuth)
}
export function useRestartAuth() {
  return useServerAction(serverApi.restartAuth)
}

