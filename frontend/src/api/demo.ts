import { api } from './client';
import type { Incident } from '../types/incident';

export const demoApi = {
  createIncident: () => api.post<Incident>('/api/demo/incidents'),
};
