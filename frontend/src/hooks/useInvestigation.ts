import { useState, useEffect, useCallback } from 'react';
import { investigationsApi } from '../api/investigations';
import type { InvestigationState } from '../types/agent';

export function useInvestigation(incidentId: string | undefined) {
  const [state, setState] = useState<InvestigationState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!incidentId) return;
    setLoading(true);
    try {
      const data = await investigationsApi.get(incidentId);
      setState(data.state);
      setError(null);
    } catch {
      setState(null);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => { refresh(); }, [refresh]);

  const startInvestigation = useCallback(async () => {
    if (!incidentId) return;
    setLoading(true);
    try {
      await investigationsApi.start(incidentId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start');
    } finally {
      setLoading(false);
    }
  }, [incidentId, refresh]);

  return { state, loading, error, refresh, startInvestigation };
}
