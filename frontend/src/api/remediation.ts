import { api } from './client';
import type { RemediationProposal } from '../types/remediation';

export const remediationApi = {
  list: (incidentId: string) =>
    api.get<{ proposals: RemediationProposal[]; total: number }>(
      `/api/incidents/${incidentId}/remediation`
    ),
  approve: (remediationId: string, approvedBy: string) =>
    api.post<{ status: string }>(
      `/api/remediations/${remediationId}/approve?approved_by=${encodeURIComponent(approvedBy)}`
    ),
  reject: (remediationId: string, rejectedBy: string) =>
    api.post<{ status: string }>(
      `/api/remediations/${remediationId}/reject?rejected_by=${encodeURIComponent(rejectedBy)}`
    ),
};
