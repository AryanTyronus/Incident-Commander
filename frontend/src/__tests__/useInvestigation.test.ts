import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useInvestigation } from '../hooks/useInvestigation';
import { investigationState } from '../test/fixtures';

const INCIDENT_ID = 'inc-42';
const INVESTIGATE_URL = `/api/incidents/${INCIDENT_ID}/investigate`;
const INVESTIGATION_URL = `/api/incidents/${INCIDENT_ID}/investigation`;

type FetchCall = [string, RequestInit | undefined];

/** Minimal Response stand-in for the paths the api client touches. */
function jsonResponse(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) };
}

/**
 * Route fetches by URL so a test can describe backend behaviour rather than
 * call order: the hook issues a GET on mount and a POST + GET on start.
 */
function stubBackend(overrides: {
  investigation?: () => unknown;
  investigate?: () => unknown;
} = {}) {
  const calls: FetchCall[] = [];
  const mockFetch = vi.fn((url: string, options?: RequestInit) => {
    calls.push([url, options]);
    if (url === INVESTIGATE_URL) {
      return Promise.resolve(
        overrides.investigate?.() ??
          jsonResponse(202, {
            incident_id: INCIDENT_ID,
            investigation_status: 'PLANNING',
            message: 'Investigation accepted and running in the background',
          })
      );
    }
    if (url === INVESTIGATION_URL) {
      return Promise.resolve(
        overrides.investigation?.() ??
          jsonResponse(200, {
            incident_id: INCIDENT_ID,
            stage: 'PLANNING',
            state: { ...investigationState, status: 'PLANNING' },
          })
      );
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not Found' }));
  });
  vi.stubGlobal('fetch', mockFetch);
  return { calls, mockFetch };
}

function postCalls(calls: FetchCall[]) {
  return calls.filter(([url, options]) => url === INVESTIGATE_URL && options?.method === 'POST');
}

describe('useInvestigation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts to the investigate endpoint when started', async () => {
    const { calls } = stubBackend();
    const { result } = renderHook(() => useInvestigation(INCIDENT_ID));

    await act(async () => { await result.current.startInvestigation(); });

    expect(postCalls(calls)).toHaveLength(1);
    expect(postCalls(calls)[0][1]?.method).toBe('POST');
  });

  it('treats a 202 Accepted as success', async () => {
    stubBackend();
    const { result } = renderHook(() => useInvestigation(INCIDENT_ID));

    await act(async () => { await result.current.startInvestigation(); });

    expect(result.current.error).toBeNull();
    expect(result.current.starting).toBe(false);
  });

  it('does not wait for the investigation to finish', async () => {
    // The backend answers while the investigation is still PLANNING; the hook
    // must return then, not block until COMPLETED.
    stubBackend();
    const { result } = renderHook(() => useInvestigation(INCIDENT_ID));

    await act(async () => { await result.current.startInvestigation(); });

    expect(result.current.starting).toBe(false);
    expect(result.current.state?.status).toBe('PLANNING');
  });

  it('does not poll after starting', async () => {
    vi.useFakeTimers();
    try {
      const { calls } = stubBackend();
      const { result } = renderHook(() => useInvestigation(INCIDENT_ID));
      await act(async () => { await result.current.startInvestigation(); });
      const afterStart = calls.length;

      await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });

      expect(calls.length).toBe(afterStart);
    } finally {
      vi.useRealTimers();
    }
  });

  it('tolerates a 404 from the investigation GET', async () => {
    // Right after a start there may be no persisted investigation yet.
    stubBackend({ investigation: () => jsonResponse(404, { detail: 'No investigation found' }) });
    const { result } = renderHook(() => useInvestigation(INCIDENT_ID));

    await act(async () => { await result.current.startInvestigation(); });

    expect(result.current.state).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('surfaces an error when the start request is rejected', async () => {
    stubBackend({
      investigate: () => jsonResponse(409, { detail: 'Investigation already running' }),
    });
    const { result } = renderHook(() => useInvestigation(INCIDENT_ID));

    await act(async () => { await result.current.startInvestigation(); });

    expect(result.current.error).toBe('Investigation already running');
    expect(result.current.starting).toBe(false);
  });

  it('loads existing investigation state on mount', async () => {
    stubBackend();
    const { result } = renderHook(() => useInvestigation(INCIDENT_ID));

    await waitFor(() => expect(result.current.state).not.toBeNull());
    expect(result.current.state?.incident_id).toBe(investigationState.incident_id);
  });

  it('does nothing without an incident id', async () => {
    const { calls } = stubBackend();
    const { result } = renderHook(() => useInvestigation(undefined));

    await act(async () => { await result.current.startInvestigation(); });

    expect(calls).toHaveLength(0);
  });
});
