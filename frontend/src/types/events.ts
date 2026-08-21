export interface IncidentEvent {
  id: string;
  incident_id: string;
  event_type: string;
  timestamp: string;
  agent_name: string | null;
  payload: Record<string, unknown>;
  sequence: number;
}
