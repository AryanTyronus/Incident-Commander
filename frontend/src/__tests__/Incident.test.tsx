import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

describe('IncidentPage investigate flow', () => {
  let startInvestigation: ReturnType<typeof vi.fn>;
  let refresh: ReturnType<typeof vi.fn>;

  /** Mock the hook with the full shape the page consumes. */
  function mockInvestigation(overrides: Record<string, unknown> = {}) {
    (useInvestigation as ReturnType<typeof vi.fn>).mockReturnValue({
      state: investigationState,
      loading: false,
      starting: false,
      error: null,
      refresh,
      startInvestigation,
      ...overrides,
    });
  }

  function streamEvent(sequence: number, event_type: string) {
    return {
      id: `evt-${sequence}`,
      incident_id: incident.id,
      event_type,
      timestamp: '2026-08-21T10:00:00Z',
      agent_name: null,
      payload: {},
      sequence,
    };
  }

  beforeEach(() => {
    vi.clearAllMocks();
    startInvestigation = vi.fn().mockResolvedValue(undefined);
    refresh = vi.fn().mockResolvedValue(undefined);
    (useIncident as ReturnType<typeof vi.fn>).mockReturnValue({ incident, loading: false, error: null });
    (useIncidentStream as ReturnType<typeof vi.fn>).mockReturnValue({ events: [], connected: true });
    (evidenceApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ evidence, total: 4 });
    (evidenceApi.listFindings as ReturnType<typeof vi.fn>).mockResolvedValue({ findings, total: 1 });
    (rcaApi.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No RCA'));
    (remediationApi.list as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('No proposals'));
    mockInvestigation();
  });

  it('calls the API when Investigate is clicked', async () => {
    renderIncidentPage();
    const button = await screen.findByRole('button', { name: /^Investigate$/ });

    await userEvent.click(button);

    expect(startInvestigation).toHaveBeenCalledTimes(1);
  });

  it('does not wait for the investigation before returning to the UI', async () => {
    // A start request that never resolves must not freeze the page: the other
    // controls stay interactive because nothing awaits completion in render.
    startInvestigation.mockReturnValue(new Promise(() => {}));
    renderIncidentPage();
    const button = await screen.findByRole('button', { name: /^Investigate$/ });

    await userEvent.click(button);

    expect(screen.getByRole('button', { name: /Analyze.*RCA/i })).toBeEnabled();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
  });

  it('shows an investigating state while the request is in flight', async () => {
    mockInvestigation({ starting: true });
    renderIncidentPage();

    const button = await screen.findByRole('button', { name: /Investigating/i });
    expect(button).toBeDisabled();
  });

  it('shows an investigating state while the backend is still working', async () => {
    mockInvestigation({ state: { ...investigationState, status: 'EXECUTING' } });
    renderIncidentPage();

    const button = await screen.findByRole('button', { name: /Investigating/i });
    expect(button).toBeDisabled();
    expect(screen.getByTestId('investigation-stage')).toHaveTextContent('EXECUTING');
  });

  it('re-enables Investigate once the investigation finishes', async () => {
    renderIncidentPage();

    const button = await screen.findByRole('button', { name: /^Investigate$/ });
    expect(button).toBeEnabled();
    expect(screen.getByTestId('investigation-stage')).toHaveTextContent('COMPLETED');
  });

  it('surfaces a start failure', async () => {
    mockInvestigation({ error: 'Investigation already running' });
    renderIncidentPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Investigation already running');
    });
  });

  it('refreshes investigation state from streamed events', async () => {
    (useIncidentStream as ReturnType<typeof vi.fn>).mockReturnValue({
      events: [streamEvent(1, 'INVESTIGATION_STARTED'), streamEvent(2, 'INVESTIGATION_STAGE_CHANGED')],
      connected: true,
    });
    renderIncidentPage();

    await waitFor(() => expect(refresh).toHaveBeenCalled());
  });

  it('renders streamed progress events on the timeline', async () => {
    (useIncidentStream as ReturnType<typeof vi.fn>).mockReturnValue({
      events: [streamEvent(1, 'AGENT_STARTED')],
      connected: true,
    });
    renderIncidentPage();

    await waitFor(() => expect(screen.getByText(/AGENT_STARTED/)).toBeInTheDocument());
  });

  it('ignores unrelated events instead of refreshing', async () => {
    (useIncidentStream as ReturnType<typeof vi.fn>).mockReturnValue({
      events: [streamEvent(1, 'INCIDENT_CREATED')],
      connected: true,
    });
    renderIncidentPage();

    await waitFor(() => expect(screen.getByText('Timeline')).toBeInTheDocument());
    expect(refresh).not.toHaveBeenCalled();
  });
});

describe('IncidentPage analyze flow', () => {
  // Analyze is a plain button with nothing guarding a second press, and
  // handleAnalyze awaits rcaApi.analyze before refreshing. A backend that
  // answered 500 on the repeat left the page stale behind a rejected await, so
  // pin down that the repeat is issued and that the refresh follows every time.
  beforeEach(() => {
    vi.clearAllMocks();
    (useIncident as ReturnType<typeof vi.fn>).mockReturnValue({ incident, loading: false, error: null });
    (useInvestigation as ReturnType<typeof vi.fn>).mockReturnValue({
      state: investigationState,
      loading: false,
      starting: false,
      error: null,
      refresh: vi.fn().mockResolvedValue(undefined),
      startInvestigation: vi.fn().mockResolvedValue(undefined),
    });
    (useIncidentStream as ReturnType<typeof vi.fn>).mockReturnValue({ events: [], connected: true });
    (evidenceApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ evidence, total: 4 });
    (evidenceApi.listFindings as ReturnType<typeof vi.fn>).mockResolvedValue({ findings, total: 1 });
    (rcaApi.analyze as ReturnType<typeof vi.fn>).mockResolvedValue({
      rca: rcaData,
      remediation_proposals: remediationProposals,
      approvals: [],
    });
    (rcaApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ rca: rcaData });
    (remediationApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      proposals: remediationProposals,
      total: remediationProposals.length,
    });
  });

  async function clickAnalyze() {
    await userEvent.click(await screen.findByRole('button', { name: /Analyze.*RCA/i }));
  }

  it('posts an analyze request for the incident', async () => {
    renderIncidentPage();

    await clickAnalyze();

    expect(rcaApi.analyze).toHaveBeenCalledWith(incident.id);
  });

  it('posts a second analyze request when Analyze is clicked again', async () => {
    renderIncidentPage();

    await clickAnalyze();
    await clickAnalyze();

    expect(rcaApi.analyze).toHaveBeenCalledTimes(2);
  });

  it('refreshes the RCA after every analyze', async () => {
    renderIncidentPage();
    // One refresh on mount, then one per click.
    await waitFor(() => expect(rcaApi.get).toHaveBeenCalledTimes(1));

    await clickAnalyze();
    await clickAnalyze();

    await waitFor(() => expect(rcaApi.get).toHaveBeenCalledTimes(3));
  });

  it('still shows the RCA after a repeated analyze', async () => {
    renderIncidentPage();

    await clickAnalyze();
    await clickAnalyze();

    await waitFor(() =>
      expect(screen.getByText(rcaData.primary_hypothesis.title)).toBeInTheDocument()
    );
  });
});
