export interface Incident {
  id: string;
  source: string;
  title: string;
  severity: string;
  service: string;
  environment: string;
  status: string;
  description: string;
  stack_traces: string[];
  created_at: string;
  updated_at: string;
  raw_payload: Record<string, unknown>;
}

export interface IncidentListResponse {
  incidents: Incident[];
  total: number;
  limit: number;
  offset: number;
}
