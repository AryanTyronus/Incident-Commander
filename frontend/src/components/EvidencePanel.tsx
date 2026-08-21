import { useState } from 'react';
import type { Evidence } from '../types/evidence';

const typeFilters = ['ALL', 'LOG', 'STACK_TRACE', 'GIT_COMMIT', 'GIT_DIFF', 'RUNBOOK'];

export function EvidencePanel({ evidence }: { evidence: Evidence[] }) {
  const [filter, setFilter] = useState('ALL');
  const filtered = filter === 'ALL' ? evidence : evidence.filter(e => e.source_type === filter);

  return (
    <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', background: '#1a1a2e' }}>
      <h3 style={{ margin: '0 0 12px', color: '#fff', fontSize: '14px' }}>Evidence ({evidence.length})</h3>
      <div style={{ display: 'flex', gap: '4px', marginBottom: '12px', flexWrap: 'wrap' }}>
        {typeFilters.map(type => (
          <button key={type} onClick={() => setFilter(type)}
            style={{ padding: '4px 8px', borderRadius: '4px', border: 'none', cursor: 'pointer',
              fontSize: '11px', background: filter === type ? '#3b82f6' : '#374151', color: '#fff' }}>
            {type}
          </button>
        ))}
      </div>
      <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
        {filtered.map((item, i) => (
          <div key={i} style={{ padding: '8px', marginBottom: '8px', borderRadius: '4px',
            background: '#111827', border: '1px solid #333' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ color: '#93c5fd', fontSize: '12px', fontWeight: 'bold' }}>
                {item.source_type}
              </span>
              <span style={{ color: '#6b7280', fontSize: '11px' }}>{item.source_reference}</span>
            </div>
            <pre style={{ margin: 0, color: '#d1d5db', fontSize: '11px', whiteSpace: 'pre-wrap',
              maxHeight: '100px', overflow: 'auto' }}>
              {item.content}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
