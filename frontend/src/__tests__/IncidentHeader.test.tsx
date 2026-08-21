import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { IncidentHeader } from '../components/IncidentHeader';
import { incident } from '../test/fixtures';

describe('IncidentHeader', () => {
  it('renders incident title', () => {
    render(<IncidentHeader incident={incident} />);
    expect(screen.getByText('Payment service outage - validation regression')).toBeInTheDocument();
  });

  it('renders severity badge', () => {
    render(<IncidentHeader incident={incident} />);
    expect(screen.getByText('SEV1')).toBeInTheDocument();
  });

  it('renders status', () => {
    render(<IncidentHeader incident={incident} />);
    expect(screen.getByText('INVESTIGATING')).toBeInTheDocument();
  });

  it('renders service and environment', () => {
    render(<IncidentHeader incident={incident} />);
    expect(screen.getByText(/payment-service/)).toBeInTheDocument();
    expect(screen.getByText(/production/)).toBeInTheDocument();
  });

  it('renders incident ID', () => {
    render(<IncidentHeader incident={incident} />);
    expect(screen.getByText(new RegExp(incident.id))).toBeInTheDocument();
  });

  it('renders elapsed time', () => {
    render(<IncidentHeader incident={incident} />);
    expect(screen.getByText(/Elapsed/)).toBeInTheDocument();
  });
});
