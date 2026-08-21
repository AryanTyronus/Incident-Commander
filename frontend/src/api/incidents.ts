import { api } from './client';
import type { Incident, IncidentListResponse } from '../types/incident';

export const incidentsApi = {
  list: (limit = 50, offset = 0) =>
    api.get<IncidentListResponse>(`/api/incidents?limit=${limit}&offset=${offset}`),
  get: (id: string) => api.get<Incident>(`/api/incidents/${id}`),
  create: (data: Partial<Incident>) => api.post<Incident>('/api/incidents', data),
};
