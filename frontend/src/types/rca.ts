export interface RootCauseHypothesis {
  id: string;
  title: string;
  explanation: string;
  confidence: number;
}

export interface RCA {
  id: string;
  incident_id: string;
  primary_hypothesis: RootCauseHypothesis;
  alternative_hypotheses: RootCauseHypothesis[];
  confidence: number;
  confidence_band: string;
  observed_facts: string[];
  inferred_facts: string[];
  uncertainties: string[];
  created_at: string;
}
