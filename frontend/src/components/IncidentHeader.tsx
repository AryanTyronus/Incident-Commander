import type { Incident } from '../types/incident';

const severityColors: Record<string, string> = {
  SEV1: '#ef4444', SEV2: '#f97316', SEV3: '#eab308', SEV4: '#6b7280',
};

export function IncidentHeader({ incident }: { incident: Incident }) {
  const mins = Math.floor((Date.now() - new Date(incident.created_at).getTime()) / 60000);
  return (
    <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px', background: '#1a1a2e' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0, color: '#fff' }}>{incident.title}</h2>
          <p style={{ margin: '4px 0', color: '#9ca3af', fontSize: '14px' }}>
            {incident.service} &middot; {incident.environment} &middot; {incident.source}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ padding: '4px 12px', borderRadius: '4px', fontWeight: 'bold',
            background: severityColors[incident.severity] || '#6b7280', color: '#fff', fontSize: '12px' }}>
            {incident.severity}
          </span>
          <span style={{ padding: '4px 12px', borderRadius: '4px',
            background: '#374151', color: '#d1d5db', fontSize: '12px' }}>
            {incident.status}
          </span>
        </div>
      </div>
      <p style={{ margin: '8px 0 0', color: '#9ca3af', fontSize: '12px' }}>
        ID: {incident.id} &middot; Elapsed: {mins}m
      </p>
    </div>
  );
}
