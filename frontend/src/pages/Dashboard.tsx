import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { incidentsApi } from '../api/incidents';
import { demoApi } from '../api/demo';
import type { Incident } from '../types/incident';

export function Dashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    incidentsApi.list().then(d => { setIncidents(d.incidents); setLoading(false); });
  }, []);

  const handleDemo = async () => {
    const inc = await demoApi.createIncident();
    window.location.href = `/incidents/${inc.id}`;
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px' }}>
        <h1 style={{ color: '#fff', margin: 0 }}>Incident Commander</h1>
        <button onClick={handleDemo}
          style={{ padding: '8px 16px', borderRadius: '6px', border: 'none',
            background: '#8b5cf6', color: '#fff', cursor: 'pointer', fontWeight: 'bold' }}>
          Replay Demo Incident
        </button>
      </div>
      {loading ? <p style={{ color: '#6b7280' }}>Loading...</p>
        : incidents.length === 0
          ? <p style={{ color: '#6b7280' }}>No incidents. Click &quot;Replay Demo Incident&quot;.</p>
          : (
            <div style={{ display: 'grid', gap: '12px' }}>
              {incidents.map(inc => (
                <Link key={inc.id} to={`/incidents/${inc.id}`} style={{ textDecoration: 'none' }}>
                  <div style={{ padding: '16px', borderRadius: '8px', border: '1px solid #333',
                    background: '#1a1a2e', display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center' }}>
                    <div>
                      <div style={{ color: '#fff', fontWeight: 'bold' }}>{inc.title}</div>
                      <div style={{ color: '#9ca3af', fontSize: '12px', marginTop: '4px' }}>
                        {inc.service} &middot; {inc.environment}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span style={{ padding: '4px 8px', borderRadius: '4px',
                        background: inc.severity === 'SEV1' ? '#ef4444' : '#6b7280',
                        color: '#fff', fontSize: '11px' }}>
                        {inc.severity}
                      </span>
                      <span style={{ color: '#9ca3af', fontSize: '12px' }}>{inc.status}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
    </div>
  );
}
