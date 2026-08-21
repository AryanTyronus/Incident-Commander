import type { Incident } from '../types/incident';
import type { AgentRun, InvestigationState } from '../types/agent';
import type { Evidence, Finding } from '../types/evidence';
import type { RCA } from '../types/rca';
import type { RemediationProposal } from '../types/remediation';
import type { IncidentEvent } from '../types/events';

export const INCIDENT_ID = '00000000-0000-4000-8000-000000000001';

export const incident: Incident = {
  id: INCIDENT_ID,
  source: 'datadog',
  title: 'Payment service outage - validation regression',
  severity: 'SEV1',
  service: 'payment-service',
  environment: 'production',
  status: 'INVESTIGATING',
  description: 'Payment validation failing for all transactions',
  stack_traces: ['Error: validation failed at PaymentValidator.process'],
  created_at: '2026-08-21T10:00:00Z',
  updated_at: '2026-08-21T10:05:00Z',
  raw_payload: {},
};

export const incident2: Incident = {
  id: '00000000-0000-4000-8000-000000000002',
  source: 'pagerduty',
  title: 'Auth service timeout',
  severity: 'SEV2',
  service: 'auth-service',
  environment: 'staging',
  status: 'OPEN',
  description: 'Auth timeouts increasing',
  stack_traces: [],
  created_at: '2026-08-21T11:00:00Z',
  updated_at: '2026-08-21T11:00:00Z',
  raw_payload: {},
};

export const incidentsList = [incident, incident2];

export const agentRuns: AgentRun[] = [
  {
    id: 'run-1',
    incident_id: INCIDENT_ID,
    agent_name: 'log_triage',
    status: 'COMPLETED',
    started_at: '2026-08-21T10:01:00Z',
    completed_at: '2026-08-21T10:01:30Z',
    input: {},
    output: { findings: [] },
    error: null,
  },
  {
    id: 'run-2',
    incident_id: INCIDENT_ID,
    agent_name: 'git_forensics',
    status: 'RUNNING',
    started_at: '2026-08-21T10:01:30Z',
    completed_at: null,
    input: {},
    output: null,
    error: null,
  },
  {
    id: 'run-3',
    incident_id: INCIDENT_ID,
    agent_name: 'runbook',
    status: 'FAILED',
    started_at: '2026-08-21T10:02:00Z',
    completed_at: null,
    input: {},
    output: null,
    error: 'Connection timeout',
  },
];

export const investigationState: InvestigationState = {
  incident_id: INCIDENT_ID,
  status: 'COMPLETED',
  active_runs: [],
  completed_runs: [agentRuns[0]],
  failed_runs: [agentRuns[2]],
  findings: [],
  errors: [],
};

export const events: IncidentEvent[] = [
  {
    id: 'evt-1',
    incident_id: INCIDENT_ID,
    event_type: 'INCIDENT_CREATED',
    timestamp: '2026-08-21T10:00:00Z',
    agent_name: null,
    payload: { title: 'Payment service outage' },
    sequence: 1,
  },
  {
    id: 'evt-2',
    incident_id: INCIDENT_ID,
    event_type: 'INVESTIGATION_STARTED',
    timestamp: '2026-08-21T10:01:00Z',
    agent_name: null,
    payload: {},
    sequence: 2,
  },
  {
    id: 'evt-3',
    incident_id: INCIDENT_ID,
    event_type: 'AGENT_COMPLETED',
    timestamp: '2026-08-21T10:01:30Z',
    agent_name: 'log_triage',
    payload: { agent_name: 'log_triage' },
    sequence: 3,
  },
  {
    id: 'evt-4',
    incident_id: INCIDENT_ID,
    event_type: 'AGENT_FAILED',
    timestamp: '2026-08-21T10:02:00Z',
    agent_name: 'runbook',
    payload: { error: 'Connection timeout' },
    sequence: 4,
  },
];

export const evidence: Evidence[] = [
  {
    id: 'ev-1',
    source_type: 'LOG',
    source_reference: '/var/log/payment-service.log',
    content: 'ERROR: validation failed for transaction tx-123',
    timestamp: '2026-08-21T10:00:00Z',
    metadata: {},
    created_at: '2026-08-21T10:01:00Z',
  },
  {
    id: 'ev-2',
    source_type: 'STACK_TRACE',
    source_reference: 'stacktrace.txt',
    content: 'Error: validation failed\n  at PaymentValidator.process\n  at PaymentService.charge',
    timestamp: '2026-08-21T10:00:00Z',
    metadata: {},
    created_at: '2026-08-21T10:01:00Z',
  },
  {
    id: 'ev-3',
    source_type: 'GIT_COMMIT',
    source_reference: 'a1b2c3d',
    content: 'Commit: a1b2c3d - Refactor payment validation logic',
    timestamp: '2026-08-21T09:30:00Z',
    metadata: { author: 'dev@company.com' },
    created_at: '2026-08-21T10:01:00Z',
  },
  {
    id: 'ev-4',
    source_type: 'GIT_DIFF',
    source_reference: 'a1b2c3d',
    content: '--- a/payment.py\n+++ b/payment.py\n@@ -10, +10 @@\n- if amount > 0:\n+ if amount >= 0:',
    timestamp: '2026-08-21T09:30:00Z',
    metadata: {},
    created_at: '2026-08-21T10:01:00Z',
  },
];

export const findings: Finding[] = [
  {
    id: 'f-1',
    agent_name: 'log_triage',
    finding_type: 'ERROR_PATTERN',
    summary: 'Validation errors in payment logs',
    confidence: 0.9,
    evidence_ids: ['ev-1'],
    created_at: '2026-08-21T10:01:30Z',
    metadata: {},
  },
];

export const rcaData: RCA = {
  id: 'rca-1',
  incident_id: INCIDENT_ID,
  primary_hypothesis: {
    id: 'hyp-1',
    title: 'Validation boundary condition changed in commit a1b2c3d',
    explanation: 'The commit changed > to >= allowing zero-amount transactions that fail downstream validation.',
    confidence: 0.87,
  },
  alternative_hypotheses: [],
  confidence: 0.87,
  confidence_band: 'HIGH',
  observed_facts: [
    'Validation errors started after deploy at 09:45',
    'Commit a1b2c3d changed payment validation boundary',
  ],
  inferred_facts: [
    'Zero-amount transactions are now passing initial validation',
  ],
  uncertainties: [
    'No direct test coverage for zero-amount edge case',
  ],
  created_at: '2026-08-21T10:05:00Z',
};

export const remediationProposals: RemediationProposal[] = [
  {
    id: 'rem-1',
    type: 'ROLLBACK',
    title: 'Revert commit a1b2c3d',
    description: 'Revert the validation boundary change to restore original behavior.',
    rationale: 'The commit introduced the regression',
    expected_effect: 'Restore original validation behavior',
    risks: ['May lose unrelated changes in same commit'],
    prerequisites: ['Confirm no other changes in commit are critical'],
    commands: ['git revert a1b2c3d --no-edit'],
    patch_summary: 'Reverts boundary condition change',
    status: 'PROPOSED',
    requires_approval: true,
    created_at: '2026-08-21T10:05:00Z',
  },
  {
    id: 'rem-2',
    type: 'PATCH',
    title: 'Add explicit zero-amount guard',
    description: 'Add guard clause for zero-amount transactions.',
    rationale: 'Targeted fix without full revert',
    expected_effect: 'Block zero-amount transactions at validation',
    risks: ['May not cover all edge cases'],
    prerequisites: ['Unit tests for zero-amount scenario'],
    commands: ['if amount <= 0: raise ValueError("Amount must be positive")'],
    patch_summary: 'Adds guard clause',
    status: 'APPROVED',
    requires_approval: true,
    created_at: '2026-08-21T10:05:00Z',
  },
];
