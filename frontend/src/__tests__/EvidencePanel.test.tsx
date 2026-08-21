import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { EvidencePanel } from '../components/EvidencePanel';
import { evidence } from '../test/fixtures';

describe('EvidencePanel', () => {
  it('renders evidence header with count', () => {
    render(<EvidencePanel evidence={evidence} />);
    expect(screen.getByText('Evidence (4)')).toBeInTheDocument();
  });

  it('renders all evidence items by default', () => {
    render(<EvidencePanel evidence={evidence} />);
    const items = screen.getAllByText(/LOG|STACK_TRACE|GIT_COMMIT|GIT_DIFF/);
    const evidenceTypes = items.filter(el => el.tagName === 'SPAN');
    expect(evidenceTypes.length).toBe(4);
  });

  it('renders evidence content', () => {
    render(<EvidencePanel evidence={evidence} />);
    expect(screen.getByText(/validation failed for transaction/)).toBeInTheDocument();
  });

  it('renders source references', () => {
    render(<EvidencePanel evidence={evidence} />);
    expect(screen.getByText('/var/log/payment-service.log')).toBeInTheDocument();
    expect(screen.getByText('stacktrace.txt')).toBeInTheDocument();
  });

  it('filters by evidence type when button clicked', async () => {
    const user = userEvent.setup();
    render(<EvidencePanel evidence={evidence} />);
    await user.click(screen.getByRole('button', { name: 'LOG' }));
    const items = screen.getAllByText(/LOG|STACK_TRACE|GIT_COMMIT|GIT_DIFF/);
    const evidenceTypes = items.filter(el => el.tagName === 'SPAN');
    expect(evidenceTypes.length).toBe(1);
    expect(evidenceTypes[0].textContent).toBe('LOG');
  });

  it('shows all when ALL filter selected', async () => {
    const user = userEvent.setup();
    render(<EvidencePanel evidence={evidence} />);
    await user.click(screen.getByRole('button', { name: 'LOG' }));
    await user.click(screen.getByRole('button', { name: 'ALL' }));
    const items = screen.getAllByText(/LOG|STACK_TRACE|GIT_COMMIT|GIT_DIFF/);
    const evidenceTypes = items.filter(el => el.tagName === 'SPAN');
    expect(evidenceTypes.length).toBe(4);
  });

  it('renders empty evidence list', () => {
    render(<EvidencePanel evidence={[]} />);
    expect(screen.getByText('Evidence (0)')).toBeInTheDocument();
  });
});
