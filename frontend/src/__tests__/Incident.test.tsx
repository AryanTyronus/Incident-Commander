import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { IncidentPage } from '../pages/Incident';
import { useIncident } from '../hooks/useIncident';
import { useInvestigation } from '../hooks/useInvestigation';
import { useIncidentStream } from '../hooks/useIncidentStream';
import { evidenceApi } from '../api/evidence';
import { rcaApi } from '../api/rca';
import { remediationApi } from '../api/remediation';
import { incident, investigationState, evidence, findings, rcaData, remediationProposals } from '../test/fixtures';

vi.mock('../hooks/useIncident');
vi.mock('../hooks/useInvestigation');
vi.mock('../hooks/useIncidentStream');
vi.mock('../api/evidence');
vi.mock('../api/rca');
vi.mock('../api/remediation');

function renderIncidentPage(id = incident.id) {
  return render(
    <MemoryRouter initialEntries={[`/incidents/${id}`]}>
      <Routes>
        <Route path="/incidents/:id" element={<IncidentPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('IncidentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useIncident as ReturnType<typeof vi.fn>).mockReturnValue({ incident, loading: false, error: null });
    (useInvestigation as ReturnType<typeof vi.fn>).mockReturnValue({ state: investigationState, startInvestigation: vi.fn() });
    (useIncidentStream as ReturnType<typeof vi.fn>).mockReturnValue({ events: [], connected: false });
    (evidenceApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ evidence, total: 4 });
    (evidenceApi.listFindings as ReturnType<typeof vi.fn>).mockResolvedValue({ findings, total: 1 });
    (rcaApi.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No RCA'));
    (remediationApi.list as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No proposals'));
  });

  it('renders incident header', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText('Payment service outage - validation regression')).toBeInTheDocument();
    });
  });

  it('renders severity', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText('SEV1')).toBeInTheDocument();
    });
  });

  it('renders status', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText('INVESTIGATING')).toBeInTheDocument();
    });
  });

  it('renders service name', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText(/payment-service/)).toBeInTheDocument();
    });
  });

  it('renders Investigate button', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Investigate/i })).toBeInTheDocument();
    });
  });

  it('renders Analyze (RCA) button', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Analyze.*RCA/i })).toBeInTheDocument();
    });
  });

  it('renders agent graph', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText('Agent Execution')).toBeInTheDocument();
    });
  });

  it('renders timeline', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText('Timeline')).toBeInTheDocument();
    });
  });

  it('renders evidence panel', async () => {
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText(/Evidence/)).toBeInTheDocument();
    });
  });

  it('renders RCA panel when RCA data exists', async () => {
    (rcaApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ rca: rcaData });
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText('Root Cause Analysis')).toBeInTheDocument();
    });
  });

  it('renders remediation panel when proposals exist', async () => {
    (remediationApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ proposals: remediationProposals, total: 2 });
    renderIncidentPage();
    await waitFor(() => {
      expect(screen.getByText('Remediation')).toBeInTheDocument();
    });
  });

  it('shows loading state', () => {
    (useIncident as ReturnType<typeof vi.fn>).mockReturnValue({ incident: null, loading: true, error: null });
    renderIncidentPage();
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows not found state', () => {
    (useIncident as ReturnType<typeof vi.fn>).mockReturnValue({ incident: null, loading: false, error: null });
    renderIncidentPage();
    expect(screen.getByText('Not found')).toBeInTheDocument();
  });
});
