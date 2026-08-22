import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useIncidentStream } from '../hooks/useIncidentStream';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  url: string;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

describe('useIncidentStream', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    (globalThis as Record<string, unknown>).WebSocket = MockWebSocket;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('establishes connection on mount', () => {
    renderHook(() => useIncidentStream('inc-1'));
    expect(MockWebSocket.instances.length).toBe(1);
    expect(MockWebSocket.instances[0].url).toContain('inc-1');
  });

  it('connects to the backend stream path proxied by the dev server', () => {
    // Must stay under /api - that is the prefix vite.config.ts upgrades to a
    // WebSocket (see vite.config.test.ts).
    renderHook(() => useIncidentStream('inc-1'));
    const { pathname } = new URL(MockWebSocket.instances[0].url);
    expect(pathname).toBe('/api/incidents/inc-1/stream');
  });

  it('sets connected to true on open', () => {
    const { result } = renderHook(() => useIncidentStream('inc-1'));
    expect(result.current.connected).toBe(false);
    act(() => { MockWebSocket.instances[0].onopen?.(); });
    expect(result.current.connected).toBe(true);
  });

  it('processes valid events', () => {
    const { result } = renderHook(() => useIncidentStream('inc-1'));
    act(() => { MockWebSocket.instances[0].onopen?.(); });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({
        data: JSON.stringify({ id: 'e1', incident_id: 'inc-1', event_type: 'INCIDENT_CREATED', timestamp: '2026-01-01T00:00:00Z', agent_name: null, payload: {}, sequence: 1 }),
      });
    });
    expect(result.current.events.length).toBe(1);
    expect(result.current.events[0].event_type).toBe('INCIDENT_CREATED');
  });

  it('processes multiple events in sequence', () => {
    const { result } = renderHook(() => useIncidentStream('inc-1'));
    act(() => { MockWebSocket.instances[0].onopen?.(); });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ id: 'e1', sequence: 1, event_type: 'A', incident_id: 'inc-1', timestamp: '', agent_name: null, payload: {} }) });
    });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ id: 'e2', sequence: 2, event_type: 'B', incident_id: 'inc-1', timestamp: '', agent_name: null, payload: {} }) });
    });
    expect(result.current.events.length).toBe(2);
  });

  it('ignores duplicate sequence numbers', () => {
    const { result } = renderHook(() => useIncidentStream('inc-1'));
    act(() => { MockWebSocket.instances[0].onopen?.(); });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ id: 'e1', sequence: 1, event_type: 'A', incident_id: 'inc-1', timestamp: '', agent_name: null, payload: {} }) });
    });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ id: 'e1-dup', sequence: 1, event_type: 'A-dup', incident_id: 'inc-1', timestamp: '', agent_name: null, payload: {} }) });
    });
    expect(result.current.events.length).toBe(1);
  });

  it('ignores out-of-order sequences', () => {
    const { result } = renderHook(() => useIncidentStream('inc-1'));
    act(() => { MockWebSocket.instances[0].onopen?.(); });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ id: 'e2', sequence: 2, event_type: 'B', incident_id: 'inc-1', timestamp: '', agent_name: null, payload: {} }) });
    });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ id: 'e1', sequence: 1, event_type: 'A', incident_id: 'inc-1', timestamp: '', agent_name: null, payload: {} }) });
    });
    expect(result.current.events.length).toBe(1);
    expect(result.current.events[0].sequence).toBe(2);
  });

  it('handles malformed events gracefully', () => {
    const { result } = renderHook(() => useIncidentStream('inc-1'));
    act(() => { MockWebSocket.instances[0].onopen?.(); });
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: 'not json' });
    });
    expect(result.current.events.length).toBe(0);
  });

  it('sets connected false on close', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useIncidentStream('inc-1'));
    act(() => { MockWebSocket.instances[0].onopen?.(); });
    expect(result.current.connected).toBe(true);
    act(() => { MockWebSocket.instances[0].onclose?.(); });
    expect(result.current.connected).toBe(false);
    vi.useRealTimers();
  });

  it('cleans up on unmount', () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(() => useIncidentStream('inc-1'));
    unmount();
    expect(MockWebSocket.instances[0].closed).toBe(true);
    vi.useRealTimers();
  });
});
