import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AgentGraph } from '../components/AgentGraph';
import { agentRuns } from '../test/fixtures';

describe('AgentGraph', () => {
  it('renders agent execution header', () => {
    const { container } = render(<AgentGraph runs={[]} />);
    expect(screen.getByText('Agent Execution')).toBeInTheDocument();
    expect(container).toBeTruthy();
  });

  it('renders incident commander label', () => {
    render(<AgentGraph runs={[]} />);
    expect(screen.getByText('Incident Commander')).toBeInTheDocument();
  });

  it('shows all three agents', () => {
    render(<AgentGraph runs={[]} />);
    expect(screen.getByText('log triage')).toBeInTheDocument();
    expect(screen.getByText('git forensics')).toBeInTheDocument();
    expect(screen.getByText('runbook')).toBeInTheDocument();
  });

  it('shows PENDING status when no runs exist', () => {
    render(<AgentGraph runs={[]} />);
    const pendingStatuses = screen.getAllByText('PENDING');
    expect(pendingStatuses.length).toBe(3);
  });

  it('shows COMPLETED status for completed agent', () => {
    render(<AgentGraph runs={agentRuns} />);
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
  });

  it('shows RUNNING status for running agent', () => {
    render(<AgentGraph runs={agentRuns} />);
    expect(screen.getByText('RUNNING')).toBeInTheDocument();
  });

  it('shows FAILED status for failed agent', () => {
    render(<AgentGraph runs={agentRuns} />);
    expect(screen.getByText('FAILED')).toBeInTheDocument();
  });

  it('shows pipeline flow', () => {
    render(<AgentGraph runs={[]} />);
    expect(screen.getByText(/Findings.*RCA.*Remediation.*Approval/)).toBeInTheDocument();
  });
});
