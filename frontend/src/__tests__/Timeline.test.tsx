import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Timeline } from '../components/Timeline';
import { events } from '../test/fixtures';

describe('Timeline', () => {
  it('renders timeline header', () => {
    render(<Timeline events={[]} />);
    expect(screen.getByText('Timeline')).toBeInTheDocument();
  });

  it('shows empty state when no events', () => {
    render(<Timeline events={[]} />);
    expect(screen.getByText('No events yet')).toBeInTheDocument();
  });

  it('renders all events', () => {
    render(<Timeline events={events} />);
    expect(screen.getByText('INCIDENT_CREATED')).toBeInTheDocument();
    expect(screen.getByText('INVESTIGATION_STARTED')).toBeInTheDocument();
    expect(screen.getByText('AGENT_COMPLETED')).toBeInTheDocument();
    expect(screen.getByText('AGENT_FAILED')).toBeInTheDocument();
  });

  it('displays event types in sequence order', () => {
    render(<Timeline events={events} />);
    const eventTypes = screen.getAllByText(/INCIDENT_CREATED|INVESTIGATION_STARTED|AGENT_COMPLETED|AGENT_FAILED/);
    expect(eventTypes[0]).toHaveTextContent('INCIDENT_CREATED');
    expect(eventTypes[1]).toHaveTextContent('INVESTIGATION_STARTED');
    expect(eventTypes[2]).toHaveTextContent('AGENT_COMPLETED');
    expect(eventTypes[3]).toHaveTextContent('AGENT_FAILED');
  });

  it('displays agent names when present', () => {
    render(<Timeline events={events} />);
    expect(screen.getByText(/\[log_triage\]/)).toBeInTheDocument();
    expect(screen.getByText(/\[runbook\]/)).toBeInTheDocument();
  });

  it('displays timestamps for each event', () => {
    const { container } = render(<Timeline events={events} />);
    const timeSpans = container.querySelectorAll('span[style*="min-width: 70px"]');
    expect(timeSpans.length).toBe(4);
    for (const span of timeSpans) {
      expect(span.textContent).toMatch(/\d/);
    }
  });
});
