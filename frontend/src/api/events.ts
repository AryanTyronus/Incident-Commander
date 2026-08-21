import { api } from './client';
import type { IncidentEvent } from '../types/events';

export const eventsApi = {
  list: (incidentId: string) =>
    api.get<{ events: IncidentEvent[]; total: number }>(
      `/api/incidents/${incidentId}/events`
    ),
};
