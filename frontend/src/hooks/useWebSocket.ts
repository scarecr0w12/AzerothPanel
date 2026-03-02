import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '@/store'

interface Options {
  onMessage?: (data: string) => void
  autoReconnect?: boolean
  reconnectDelay?: number
}

export function useWebSocket(path: string, options: Options = {}) {
  const { token } = useAuthStore()
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activeRef = useRef(true)

  // Keep option callbacks in refs so they never need to be listed as
  // dependencies of `connect` – avoids a reconnect loop when the caller
  // passes an inline object literal (new reference every render).
  const onMessageRef = useRef(options.onMessage)
  const autoReconnectRef = useRef(options.autoReconnect)
  const reconnectDelayRef = useRef(options.reconnectDelay)
  useEffect(() => { onMessageRef.current = options.onMessage })
  useEffect(() => { autoReconnectRef.current = options.autoReconnect })
  useEffect(() => { reconnectDelayRef.current = options.reconnectDelay })

  const connect = useCallback(() => {
    if (!token || !activeRef.current) return

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const sep = path.includes('?') ? '&' : '?'
    const url = `${proto}://${host}${path}${sep}token=${token}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }

    ws.onmessage = (ev) => {
      onMessageRef.current?.(ev.data)
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
    }

    ws.onclose = (ev) => {
      setConnected(false)
      if (ev.code === 4001) {
        setError('Unauthorized – please log in again')
        return
      }
      if (autoReconnectRef.current !== false && activeRef.current) {
        reconnectTimer.current = setTimeout(connect, reconnectDelayRef.current ?? 3000)
      }
    }
  }, [path, token])  // options intentionally excluded – accessed via refs above

  useEffect(() => {
    activeRef.current = true
    connect()
    return () => {
      activeRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((data: string | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  return { connected, error, send }
}

