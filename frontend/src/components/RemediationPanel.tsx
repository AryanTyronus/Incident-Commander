import { useState } from 'react';
import type { RemediationProposal } from '../types/remediation';
import { remediationApi } from '../api/remediation';

export function RemediationPanel(
  { proposals, onRefresh }: { proposals: RemediationProposal[]; onRefresh: () => void }
) {
  const [engineer, setEngineer] = useState('');
  const [loading, setLoading] = useState(false);

  const handleApprove = async (id: string) => {
    if (!engineer) return;
    setLoading(true);
    try { await remediationApi.approve(id, engineer); onRefresh(); }
    finally { setLoading(false); }
  };

  const handleReject = async (id: string) => {
    if (!engineer) return;
    setLoading(true);
    try { await remediationApi.reject(id, engineer); onRefresh(); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', background: '#1a1a2e' }}>
      <h3 style={{ margin: '0 0 12px', color: '#fff', fontSize: '14px' }}>Remediation</h3>
      <div style={{ marginBottom: '12px' }}>
        <input value={engineer} onChange={e => setEngineer(e.target.value)}
          placeholder="Engineer ID"
          style={{ padding: '6px', borderRadius: '4px', border: '1px solid #555',
            background: '#111827', color: '#fff', marginRight: '8px' }} />
      </div>
      {proposals.map((p, i) => (
        <div key={i} style={{ padding: '12px', marginBottom: '8px', borderRadius: '4px',
          background: '#111827', border: '1px solid #333' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: '#93c5fd', fontWeight: 'bold' }}>[{p.type}] {p.title}</span>
            <span style={{ color: p.status === 'APPROVED' ? '#22c55e' :
              p.status === 'REJECTED' ? '#ef4444' : '#f59e0b', fontSize: '12px' }}>
              {p.status}
            </span>
          </div>
          <p style={{ color: '#d1d5db', fontSize: '12px', margin: '0 0 8px' }}>{p.description}</p>
          {p.commands.length > 0 && (
            <div style={{ marginBottom: '8px' }}>
              <div style={{ color: '#9ca3af', fontSize: '11px' }}>Commands (display only):</div>
              {p.commands.map((cmd, j) => (
                <code key={j} style={{ display: 'block', color: '#d1d5db', fontSize: '11px',
                  background: '#0d1117', padding: '4px', borderRadius: '2px', marginTop: '4px' }}>
                  {cmd}
                </code>
              ))}
            </div>
          )}
          {p.status === 'PROPOSED' && (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={() => handleApprove(p.id)} disabled={loading || !engineer}
                style={{ padding: '6px 12px', borderRadius: '4px', border: 'none',
                  background: '#22c55e', color: '#fff', cursor: 'pointer', fontSize: '12px' }}>
                Approve
              </button>
              <button onClick={() => handleReject(p.id)} disabled={loading || !engineer}
                style={{ padding: '6px 12px', borderRadius: '4px', border: 'none',
                  background: '#ef4444', color: '#fff', cursor: 'pointer', fontSize: '12px' }}>
                Reject
              </button>
            </div>
          )}
        </div>
      ))}
      <p style={{ color: '#6b7280', fontSize: '11px', marginTop: '12px' }}>
        Approval records authorization. This build does not execute production changes.
      </p>
    </div>
  );
}
