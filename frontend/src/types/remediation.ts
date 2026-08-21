export interface RemediationProposal {
  id: string;
  type: string;
  title: string;
  description: string;
  rationale: string;
  expected_effect: string;
  risks: string[];
  prerequisites: string[];
  commands: string[];
  patch_summary: string;
  status: string;
  requires_approval: boolean;
  created_at: string;
}

export interface Approval {
  id: string;
  status: string;
  approved_by: string | null;
  decided_at: string | null;
  created_at: string;
}
