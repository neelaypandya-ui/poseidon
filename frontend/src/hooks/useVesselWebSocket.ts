import { useEffect, useRef } from 'react'
import { useVesselStore, type Vessel } from '../stores/vesselStore'

const WS_URL = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000') + '/ws/vessels'

export function useVesselWebSocket() {
  const batchUpdateVessels = useVesselStore((s) => s.batchUpdateVessels)
  const wsRef = useRef<WebSocket | null>(null)
  const bufferRef = useRef<Vessel[]>([])
  const rafRef = useRef<number>(0)

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>

    function scheduleFlush() {
      if (rafRef.current) return
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = 0
        if (bufferRef.current.length === 0) return
        const batch = bufferRef.current
        bufferRef.current = []
        batchUpdateVessels(batch)
      })
    }

    function connect() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WS] Connected to vessel stream')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          bufferRef.current.push({
            mmsi: data.mmsi,
            name: data.name || null,
            ship_type: data.ship_type || 'unknown',
            destination: null,
            lon: data.lon,
            lat: data.lat,
            sog: data.sog,
            cog: data.cog,
            heading: data.heading,
            nav_status: data.nav_status,
            timestamp: data.timestamp,
          })
          scheduleFlush()
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        console.log('[WS] Disconnected, reconnecting in 3s...')
        reconnectTimer = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimer)
      cancelAnimationFrame(rafRef.current)
      wsRef.current?.close()
    }
  }, [batchUpdateVessels])
}
