export interface AgentRun {
  id: string;
  incident_id: string;
  agent_name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error: string | null;
}

export interface InvestigationState {
  incident_id: string;
  status: string;
  active_runs: AgentRun[];
  completed_runs: AgentRun[];
  failed_runs: AgentRun[];
  findings: Record<string, unknown>[];
  errors: string[];
}
