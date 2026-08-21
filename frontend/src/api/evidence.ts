import { api } from './client';
import type { Evidence, Finding } from '../types/evidence';

export const evidenceApi = {
  list: (incidentId: string) =>
    api.get<{ evidence: Evidence[]; total: number }>(
      `/api/incidents/${incidentId}/evidence`
    ),
  listFindings: (incidentId: string) =>
    api.get<{ findings: Finding[]; total: number }>(
      `/api/incidents/${incidentId}/findings`
    ),
};
