import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { RemediationPanel } from '../components/RemediationPanel';
import { remediationApi } from '../api/remediation';
import { remediationProposals } from '../test/fixtures';

vi.mock('../api/remediation', () => ({
  remediationApi: {
    list: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  },
}));

describe('RemediationPanel', () => {
  const onRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders remediation header', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    expect(screen.getByText('Remediation')).toBeInTheDocument();
  });

  it('renders proposal type and title', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    expect(screen.getByText(/\[ROLLBACK\] Revert commit a1b2c3d/)).toBeInTheDocument();
    expect(screen.getByText(/\[PATCH\] Add explicit zero-amount guard/)).toBeInTheDocument();
  });

  it('renders proposal descriptions', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    expect(screen.getByText(/Revert the validation boundary change/)).toBeInTheDocument();
  });

  it('renders commands as display only', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    const displayOnly = screen.getAllByText('Commands (display only):');
    expect(displayOnly.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('git revert a1b2c3d --no-edit')).toBeInTheDocument();
  });

  it('shows display only warning', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    expect(screen.getByText(/does not execute production changes/)).toBeInTheDocument();
  });

  it('shows approve and reject buttons for PROPOSED status', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    const approveButtons = screen.getAllByRole('button', { name: 'Approve' });
    expect(approveButtons.length).toBe(1); // Only PROPOSED gets buttons
  });

  it('does not show buttons for APPROVED status', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    const rejectButtons = screen.getAllByRole('button', { name: 'Reject' });
    expect(rejectButtons.length).toBe(1); // Only PROPOSED gets buttons
  });

  it('displays status correctly', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    expect(screen.getByText('PROPOSED')).toBeInTheDocument();
    expect(screen.getByText('APPROVED')).toBeInTheDocument();
  });

  it('approve button calls correct API', async () => {
    const user = userEvent.setup();
    (remediationApi.approve as ReturnType<typeof vi.fn>).mockResolvedValue({ status: 'APPROVED' });
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    await user.type(screen.getByPlaceholderText('Engineer ID'), 'alice');
    await user.click(screen.getAllByRole('button', { name: 'Approve' })[0]);
    await waitFor(() => {
      expect(remediationApi.approve).toHaveBeenCalledWith('rem-1', 'alice');
    });
  });

  it('reject button calls correct API', async () => {
    const user = userEvent.setup();
    (remediationApi.reject as ReturnType<typeof vi.fn>).mockResolvedValue({ status: 'REJECTED' });
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    await user.type(screen.getByPlaceholderText('Engineer ID'), 'bob');
    await user.click(screen.getAllByRole('button', { name: 'Reject' })[0]);
    await waitFor(() => {
      expect(remediationApi.reject).toHaveBeenCalledWith('rem-1', 'bob');
    });
  });

  it('approve button disabled without engineer ID', () => {
    render(<RemediationPanel proposals={remediationProposals} onRefresh={onRefresh} />);
    const approveBtn = screen.getAllByRole('button', { name: 'Approve' })[0];
    expect(approveBtn).toBeDisabled();
  });
});
