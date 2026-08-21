import { useState, useEffect, useRef, useCallback } from 'react';
import type { IncidentEvent } from '../types/events';

export function useIncidentStream(incidentId: string | undefined) {
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number>(0);
  const seqRef = useRef(0);

  const connect = useCallback(() => {
    if (!incidentId) return;
    const url = `ws://${window.location.host}/api/incidents/${incidentId}/stream`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      reconnectRef.current = window.setTimeout(connect, 3000);
    };
    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as IncidentEvent;
        if (event.sequence > seqRef.current) {
          seqRef.current = event.sequence;
          setEvents(prev => [...prev, event]);
        }
      } catch { /* ignore */ }
    };
  }, [incidentId]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  return { events, connected };
}
