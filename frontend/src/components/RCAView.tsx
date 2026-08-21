import type { RCA } from '../types/rca';

const bandColors: Record<string, string> = {
  LOW: '#ef4444', MEDIUM: '#f97316', HIGH: '#22c55e', VERY_HIGH: '#10b981',
};

export function RCAView({ rca }: { rca: RCA }) {
  return (
    <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', background: '#1a1a2e' }}>
      <h3 style={{ margin: '0 0 12px', color: '#fff', fontSize: '14px' }}>Root Cause Analysis</h3>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
        <div>
          <div style={{ color: '#9ca3af', fontSize: '12px' }}>Confidence</div>
          <div style={{ color: '#fff', fontSize: '24px', fontWeight: 'bold' }}>
            {Math.round(rca.confidence * 100)}%
          </div>
          <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
            background: bandColors[rca.confidence_band] || '#6b7280', color: '#fff' }}>
            {rca.confidence_band}
          </span>
        </div>
      </div>
      <div style={{ marginBottom: '12px' }}>
        <h4 style={{ color: '#fff', margin: '0 0 8px', fontSize: '13px' }}>Primary Hypothesis</h4>
        <div style={{ color: '#d1d5db', fontSize: '13px' }}>{rca.primary_hypothesis.title}</div>
        <div style={{ color: '#9ca3af', fontSize: '12px', marginTop: '4px' }}>
          {rca.primary_hypothesis.explanation}
        </div>
      </div>
      {rca.observed_facts.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <h4 style={{ color: '#22c55e', margin: '0 0 8px', fontSize: '13px' }}>Observed Facts</h4>
          {rca.observed_facts.map((f, i) => (
            <div key={i} style={{ color: '#d1d5db', fontSize: '12px' }}>&bull; {f}</div>
          ))}
        </div>
      )}
      {rca.inferred_facts.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <h4 style={{ color: '#f59e0b', margin: '0 0 8px', fontSize: '13px' }}>Inferred Facts</h4>
          {rca.inferred_facts.map((f, i) => (
            <div key={i} style={{ color: '#d1d5db', fontSize: '12px' }}>&bull; {f}</div>
          ))}
        </div>
      )}
      {rca.uncertainties.length > 0 && (
        <div>
          <h4 style={{ color: '#ef4444', margin: '0 0 8px', fontSize: '13px' }}>Uncertainties</h4>
          {rca.uncertainties.map((u, i) => (
            <div key={i} style={{ color: '#d1d5db', fontSize: '12px' }}>&bull; {u}</div>
          ))}
        </div>
      )}
    </div>
  );
}
