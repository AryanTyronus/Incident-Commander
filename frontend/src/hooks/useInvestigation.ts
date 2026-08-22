import { useState, useEffect, useCallback } from 'react';
import { investigationsApi } from '../api/investigations';
import type { InvestigationState } from '../types/agent';

export function useInvestigation(incidentId: string | undefined) {
  const [state, setState] = useState<InvestigationState | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!incidentId) return;
    setLoading(true);
    try {
      const data = await investigationsApi.get(incidentId);
      setState(data.state);
      setError(null);
    } catch {
      // A 404 here just means no investigation exists for this incident yet -
      // expected right after a start, before the background task persists state.
      setState(null);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => { refresh(); }, [refresh]);

  const startInvestigation = useCallback(async () => {
    if (!incidentId) return;
    setStarting(true);
    setError(null);
    try {
      // The backend answers 202 as soon as the work is queued. Progress arrives
      // over the incident WebSocket, so never await completion here.
      await investigationsApi.start(incidentId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start');
    } finally {
      setStarting(false);
    }
  }, [incidentId, refresh]);

  return { state, loading, starting, error, refresh, startInvestigation };
}
