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

  const connect = useCallback(() => {
    if (!token || !activeRef.current) return

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${proto}://${host}${path}?token=${token}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }

    ws.onmessage = (ev) => {
      options.onMessage?.(ev.data)
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
      if (options.autoReconnect !== false && activeRef.current) {
        reconnectTimer.current = setTimeout(connect, options.reconnectDelay ?? 3000)
      }
    }
  }, [path, token, options])

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

