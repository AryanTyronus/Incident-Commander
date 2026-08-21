import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Dashboard } from '../pages/Dashboard';
import { incidentsApi } from '../api/incidents';
import { demoApi } from '../api/demo';
import { incidentsList, incident } from '../test/fixtures';

vi.mock('../api/incidents', () => ({
  incidentsApi: { list: vi.fn(), get: vi.fn(), create: vi.fn() },
}));

vi.mock('../api/demo', () => ({
  demoApi: { createIncident: vi.fn() },
}));

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (incidentsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      incidents: incidentsList,
      total: 2,
      limit: 50,
      offset: 0,
    });
  });

  it('renders incidents returned by the API', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('Payment service outage - validation regression')).toBeInTheDocument();
      expect(screen.getByText('Auth service timeout')).toBeInTheDocument();
    });
  });

  it('displays incident severity and status', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('SEV1')).toBeInTheDocument();
      expect(screen.getByText('SEV2')).toBeInTheDocument();
      expect(screen.getByText('INVESTIGATING')).toBeInTheDocument();
      expect(screen.getByText('OPEN')).toBeInTheDocument();
    });
  });

  it('displays service names', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText(/payment-service/)).toBeInTheDocument();
      expect(screen.getByText(/auth-service/)).toBeInTheDocument();
    });
  });

  it('renders empty state when no incidents exist', async () => {
    (incidentsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      incidents: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText(/No incidents/)).toBeInTheDocument();
    });
  });

  it('shows loading state initially', () => {
    (incidentsApi.list as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    renderDashboard();
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('has Replay Demo Incident button', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Replay Demo Incident/i })).toBeInTheDocument();
    });
  });

  it('calling demo button triggers demo API', async () => {
    const user = userEvent.setup();
    (demoApi.createIncident as ReturnType<typeof vi.fn>).mockResolvedValue(incident);
    const hrefSetter = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { ...window.location, set href(v: string) { hrefSetter(v); }, get href() { return ''; } },
      writable: true,
    });

    renderDashboard();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Replay Demo Incident/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /Replay Demo Incident/i }));
    expect(demoApi.createIncident).toHaveBeenCalled();
  });
});
