import type { AgentRun } from '../types/agent';

const statusColors: Record<string, string> = {
  PENDING: '#6b7280', RUNNING: '#3b82f6', COMPLETED: '#22c55e', FAILED: '#ef4444',
};

const agents = ['log_triage', 'git_forensics', 'runbook'];

export function AgentGraph({ runs }: { runs: AgentRun[] }) {
  const getStatus = (name: string) => runs.find(r => r.agent_name === name)?.status || 'PENDING';

  return (
    <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', background: '#1a1a2e' }}>
      <h3 style={{ margin: '0 0 12px', color: '#fff', fontSize: '14px' }}>Agent Execution</h3>
      <div style={{ textAlign: 'center', color: '#fff', fontWeight: 'bold', marginBottom: '4px' }}>
        Incident Commander
      </div>
      <div style={{ textAlign: 'center', color: '#4b5563', margin: '4px 0' }}>&#9474;</div>
      <div style={{ display: 'flex', justifyContent: 'space-around' }}>
        {agents.map(name => {
          const s = getStatus(name);
          return (
            <div key={name} style={{ padding: '8px 16px', borderRadius: '6px',
              border: `2px solid ${statusColors[s]}`, background: '#111827',
              color: '#fff', fontSize: '12px', textAlign: 'center', minWidth: '100px' }}>
              <div style={{ fontWeight: 'bold' }}>{name.replace('_', ' ')}</div>
              <div style={{ color: statusColors[s], marginTop: '4px' }}>{s}</div>
            </div>
          );
        })}
      </div>
      <div style={{ textAlign: 'center', color: '#4b5563', margin: '4px 0' }}>&#9474;</div>
      <div style={{ textAlign: 'center' }}>
        <span style={{ padding: '6px 12px', borderRadius: '4px', background: '#1e3a5f',
          color: '#93c5fd', fontSize: '12px' }}>
          Findings &rarr; RCA &rarr; Remediation &rarr; Approval
        </span>
      </div>
    </div>
  );
}
