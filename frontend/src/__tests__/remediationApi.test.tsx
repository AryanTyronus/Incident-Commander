import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { remediationApi } from '../api/remediation';
import { RemediationPanel } from '../components/RemediationPanel';
import type { RemediationProposal } from '../types/remediation';

/**
 * These tests use the REAL remediation API module (RemediationPanel.test.tsx
 * mocks it, so it can never catch a wrong URL) and assert the exact request the
 * backend has to answer. Approve/Reject were posting to /api/remediations/...
 * while the routes were registered under /api/incidents/remediations/..., so
 * every decision came back 404.
 */

const REMEDIATION_ID = '1c844ed6-8f2b-4012-b07c-c60392d9fff6';
const ENGINEER = 'demo-engineer';

function stubFetch() {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ status: 'REJECTED' }),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function lastRequest(fetchMock: ReturnType<typeof stubFetch>) {
  const [url, options] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  return { url: url as string, options: options as RequestInit };
}

const proposal: RemediationProposal = {
  id: REMEDIATION_ID,
  type: 'ROLLBACK',
  title: 'Revert commit 7666d11',
  description: 'Revert the validation boundary change',
  rationale: 'The regression was introduced there',
  expected_effect: 'Validation rejects negative amounts again',
  risks: [],
  prerequisites: [],
  commands: ['git revert 7666d11 --no-edit'],
  patch_summary: '',
  status: 'PROPOSED',
  requires_approval: true,
  created_at: '2026-08-22T10:00:00Z',
};

describe('remediationApi request shape', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts a rejection to /api/remediations/{id}/reject', async () => {
    const fetchMock = stubFetch();

    await remediationApi.reject(REMEDIATION_ID, ENGINEER);

    const { url, options } = lastRequest(fetchMock);
    expect(url).toBe(`/api/remediations/${REMEDIATION_ID}/reject?rejected_by=${ENGINEER}`);
    expect(options.method).toBe('POST');
  });

  it('posts an approval to /api/remediations/{id}/approve', async () => {
    const fetchMock = stubFetch();

    await remediationApi.approve(REMEDIATION_ID, ENGINEER);

    const { url, options } = lastRequest(fetchMock);
    expect(url).toBe(`/api/remediations/${REMEDIATION_ID}/approve?approved_by=${ENGINEER}`);
    expect(options.method).toBe('POST');
  });

  it('does not nest the decision routes under /api/incidents', async () => {
    const fetchMock = stubFetch();

    await remediationApi.reject(REMEDIATION_ID, ENGINEER);
    await remediationApi.approve(REMEDIATION_ID, ENGINEER);

    for (const [url] of fetchMock.mock.calls) {
      expect(url as string).not.toContain('/api/incidents/remediations');
    }
  });

  it('url-encodes the engineer id', async () => {
    const fetchMock = stubFetch();

    await remediationApi.reject(REMEDIATION_ID, 'on-call engineer&admin');

    expect(lastRequest(fetchMock).url).toBe(
      `/api/remediations/${REMEDIATION_ID}/reject?rejected_by=on-call%20engineer%26admin`
    );
  });

  it('reads proposals from the incident-scoped list route', async () => {
    const fetchMock = stubFetch();

    await remediationApi.list('inc-1');

    expect(lastRequest(fetchMock).url).toBe('/api/incidents/inc-1/remediation');
  });
});

describe('RemediationPanel wired to the real API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends the engineer id from the input when Reject is clicked', async () => {
    const fetchMock = stubFetch();
    const user = userEvent.setup();
    render(<RemediationPanel proposals={[proposal]} onRefresh={vi.fn()} />);

    await user.type(screen.getByPlaceholderText('Engineer ID'), ENGINEER);
    await user.click(screen.getByText('Reject'));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const { url, options } = lastRequest(fetchMock);
    expect(url).toBe(`/api/remediations/${REMEDIATION_ID}/reject?rejected_by=${ENGINEER}`);
    expect(options.method).toBe('POST');
  });

  it('sends the engineer id from the input when Approve is clicked', async () => {
    const fetchMock = stubFetch();
    const user = userEvent.setup();
    render(<RemediationPanel proposals={[proposal]} onRefresh={vi.fn()} />);

    await user.type(screen.getByPlaceholderText('Engineer ID'), ENGINEER);
    await user.click(screen.getByText('Approve'));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(lastRequest(fetchMock).url).toBe(
      `/api/remediations/${REMEDIATION_ID}/approve?approved_by=${ENGINEER}`
    );
  });
});
