import { api } from './client';
import type { InvestigationState } from '../types/agent';

export const investigationsApi = {
  get: (incidentId: string) =>
    api.get<{ incident_id: string; stage: string; state: InvestigationState }>(
      `/api/incidents/${incidentId}/investigation`
    ),
  start: (incidentId: string) =>
    api.post<{ incident_id: string; investigation_status: string }>(
      `/api/incidents/${incidentId}/investigate`
    ),
};
