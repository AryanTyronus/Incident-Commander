import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useIncident } from '../hooks/useIncident';
import { useInvestigation } from '../hooks/useInvestigation';
import { useIncidentStream } from '../hooks/useIncidentStream';
import { evidenceApi } from '../api/evidence';
import { rcaApi } from '../api/rca';
import { remediationApi } from '../api/remediation';
import { IncidentHeader } from '../components/IncidentHeader';
import { AgentGraph } from '../components/AgentGraph';
import { Timeline } from '../components/Timeline';
import { EvidencePanel } from '../components/EvidencePanel';
import { RCAView } from '../components/RCAView';
import { RemediationPanel } from '../components/RemediationPanel';
import type { Evidence, Finding } from '../types/evidence';
import type { RCA } from '../types/rca';
import type { RemediationProposal } from '../types/remediation';

export function IncidentPage() {
  const { id } = useParams<{ id: string }>();
  const { incident, loading: incLoading } = useIncident(id);
  const { state: investigation, startInvestigation } = useInvestigation(id);
  const { events } = useIncidentStream(id);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [, setFindings] = useState<Finding[]>([]);
  const [rca, setRca] = useState<RCA | null>(null);
  const [proposals, setProposals] = useState<RemediationProposal[]>([]);

  const refreshAll = async () => {
    if (!id) return;
    const [ev, fi] = await Promise.all([evidenceApi.list(id), evidenceApi.listFindings(id)]);
    setEvidence(ev.evidence);
    setFindings(fi.findings);
    try { const rc = await rcaApi.get(id); setRca(rc.rca); } catch { /* no rca */ }
    try { const rp = await remediationApi.list(id); setProposals(rp.proposals); } catch { /* */ }
  };

  useEffect(() => { refreshAll(); }, [id]);

  const handleAnalyze = async () => {
    if (!id) return;
    await rcaApi.analyze(id);
    await refreshAll();
  };

  if (incLoading) return <div style={{ padding: '24px', color: '#fff' }}>Loading...</div>;
  if (!incident) return <div style={{ padding: '24px', color: '#ef4444' }}>Not found</div>;

  const allRuns = [
    ...(investigation?.completed_runs || []),
    ...(investigation?.active_runs || []),
    ...(investigation?.failed_runs || []),
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <IncidentHeader incident={incident} />
      <div style={{ margin: '12px 0', display: 'flex', gap: '8px' }}>
        <button onClick={startInvestigation}
          style={{ padding: '8px 16px', borderRadius: '6px', border: 'none',
            background: '#3b82f6', color: '#fff', cursor: 'pointer', fontWeight: 'bold' }}>
          Investigate
        </button>
        <button onClick={handleAnalyze}
          style={{ padding: '8px 16px', borderRadius: '6px', border: 'none',
            background: '#f59e0b', color: '#fff', cursor: 'pointer', fontWeight: 'bold' }}>
          Analyze (RCA)
        </button>
        <button onClick={refreshAll}
          style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #555',
            background: 'transparent', color: '#d1d5db', cursor: 'pointer' }}>
          Refresh
        </button>
      </div>
      <AgentGraph runs={allRuns} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '12px' }}>
        <Timeline events={events} />
        <EvidencePanel evidence={evidence} />
      </div>
      {rca && <div style={{ marginTop: '12px' }}><RCAView rca={rca} /></div>}
      {proposals.length > 0 && (
        <div style={{ marginTop: '12px' }}>
          <RemediationPanel proposals={proposals} onRefresh={refreshAll} />
        </div>
      )}
    </div>
  );
}
