import type { IncidentEvent } from '../types/events';

const eventColors: Record<string, string> = {
  INCIDENT_CREATED: '#ef4444', INVESTIGATION_STARTED: '#3b82f6',
  AGENT_STARTED: '#8b5cf6', AGENT_COMPLETED: '#22c55e',
  AGENT_FAILED: '#ef4444', EVIDENCE_ADDED: '#06b6d4',
  RCA_STARTED: '#f59e0b', RCA_COMPLETED: '#22c55e',
  REMEDIATION_PROPOSED: '#8b5cf6', APPROVAL_REQUIRED: '#f97316',
  REMEDIATION_APPROVED: '#22c55e', REMEDIATION_REJECTED: '#ef4444',
};

export function Timeline({ events }: { events: IncidentEvent[] }) {
  return (
    <div style={{ padding: '16px', border: '1px solid #333', borderRadius: '8px',
      background: '#1a1a2e', maxHeight: '400px', overflowY: 'auto' }}>
      <h3 style={{ margin: '0 0 12px', color: '#fff', fontSize: '14px' }}>Timeline</h3>
      {events.length === 0 && <p style={{ color: '#6b7280' }}>No events yet</p>}
      {events.map((event, i) => (
        <div key={i} style={{ display: 'flex', gap: '12px', padding: '6px 0',
          borderBottom: '1px solid #333' }}>
          <span style={{ color: '#6b7280', fontSize: '12px', minWidth: '70px' }}>
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
          <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
            fontWeight: 'bold', background: eventColors[event.event_type] || '#374151',
            color: '#fff' }}>
            {event.event_type}
          </span>
          <span style={{ color: '#d1d5db', fontSize: '13px' }}>
            {event.agent_name && <span style={{ color: '#93c5fd' }}>[{event.agent_name}] </span>}
            {JSON.stringify(event.payload).slice(0, 80)}
          </span>
        </div>
      ))}
    </div>
  );
}
