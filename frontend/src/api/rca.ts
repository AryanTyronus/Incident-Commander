import { api } from './client';
import type { RCA } from '../types/rca';

export const rcaApi = {
  get: (incidentId: string) =>
    api.get<{ rca: RCA }>(`/api/incidents/${incidentId}/rca`),
  analyze: (incidentId: string) =>
    api.post<{ rca: RCA; remediation_proposals: unknown[]; approvals: unknown[] }>(
      `/api/incidents/${incidentId}/analyze`
    ),
};
