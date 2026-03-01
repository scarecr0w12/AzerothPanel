import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { serverApi, instancesApi } from '@/services/api'
import { toast } from '@/components/ui/Toast'
import type {
  ServerStatus, ServerActionResponse,
  WorldServerInstance, WorldServerInstanceCreate, WorldServerInstanceUpdate,
} from '@/types'

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

// ---------------------------------------------------------------------------
// Multi-instance hooks
// ---------------------------------------------------------------------------

export function useInstances(refetchInterval = 4000) {
  return useQuery<{ instances: WorldServerInstance[] }>({
    queryKey: ['worldserver-instances'],
    queryFn: () => instancesApi.list().then((r) => r.data),
    refetchInterval,
    retry: false,
  })
}

function useInstanceAction(
  fn: () => Promise<{ data: ServerActionResponse }>,
  actionName: string,
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (response) => {
      if (response.data.success) {
        toast(response.data.message || `${actionName} successful`, 'success')
      } else {
        toast(response.data.message || `${actionName} failed`, 'error')
      }
      setTimeout(() => qc.invalidateQueries({ queryKey: ['worldserver-instances'] }), 1500)
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      const message = err.response?.data?.detail || `${actionName} failed`
      toast(message, 'error')
      setTimeout(() => qc.invalidateQueries({ queryKey: ['worldserver-instances'] }), 1500)
    },
  })
}

export function useStartInstance(id: number) {
  return useInstanceAction(() => instancesApi.start(id), `Start instance ${id}`)
}
export function useStopInstance(id: number) {
  return useInstanceAction(() => instancesApi.stop(id), `Stop instance ${id}`)
}
export function useRestartInstance(id: number) {
  return useInstanceAction(() => instancesApi.restart(id), `Restart instance ${id}`)
}

export function useCreateInstance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: WorldServerInstanceCreate) =>
      instancesApi.create(data).then((r) => r.data as WorldServerInstance),
    onSuccess: () => {
      toast('Worldserver instance created', 'success')
      qc.invalidateQueries({ queryKey: ['worldserver-instances'] })
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      toast(err.response?.data?.detail || 'Failed to create instance', 'error')
    },
  })
}

export function useUpdateInstance(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: WorldServerInstanceUpdate) =>
      instancesApi.update(id, data).then((r) => r.data as WorldServerInstance),
    onSuccess: () => {
      toast('Instance updated', 'success')
      qc.invalidateQueries({ queryKey: ['worldserver-instances'] })
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      toast(err.response?.data?.detail || 'Failed to update instance', 'error')
    },
  })
}

export function useDeleteInstance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => instancesApi.delete(id).then((r) => r.data),
    onSuccess: () => {
      toast('Instance deleted', 'success')
      qc.invalidateQueries({ queryKey: ['worldserver-instances'] })
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      toast(err.response?.data?.detail || 'Failed to delete instance', 'error')
    },
  })
}

