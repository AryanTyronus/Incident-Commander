export interface Evidence {
  id: string;
  source_type: string;
  source_reference: string;
  content: string;
  timestamp: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface Finding {
  id: string;
  agent_name: string;
  finding_type: string;
  summary: string;
  confidence: number;
  evidence_ids: string[];
  created_at: string;
  metadata: Record<string, unknown>;
}
