import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../api/client';

describe('API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('makes GET request to correct path', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: 'test' }),
    });
    vi.stubGlobal('fetch', mockFetch);
    const result = await api.get('/api/test');
    expect(mockFetch).toHaveBeenCalledWith('/api/test', expect.objectContaining({
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }));
    expect(result).toEqual({ data: 'test' });
  });

  it('makes POST request with correct method and body', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: '1' }),
    });
    vi.stubGlobal('fetch', mockFetch);
    await api.post('/api/items', { name: 'test' });
    expect(mockFetch).toHaveBeenCalledWith('/api/items', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ name: 'test' }),
    }));
  });

  it('makes PATCH request with correct method', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ updated: true }),
    });
    vi.stubGlobal('fetch', mockFetch);
    await api.patch('/api/items/1', { name: 'updated' });
    expect(mockFetch).toHaveBeenCalledWith('/api/items/1', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ name: 'updated' }),
    }));
  });

  it('throws error on HTTP error with detail', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: () => Promise.resolve({ detail: 'Incident not found' }),
    });
    vi.stubGlobal('fetch', mockFetch);
    await expect(api.get('/api/missing')).rejects.toThrow('Incident not found');
  });

  it('throws HTTP status on error with empty body', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({}),
    });
    vi.stubGlobal('fetch', mockFetch);
    await expect(api.get('/api/error')).rejects.toThrow('HTTP 500');
  });

  it('falls back to statusText when JSON parse fails', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.reject(new Error('invalid json')),
    });
    vi.stubGlobal('fetch', mockFetch);
    await expect(api.get('/api/bad')).rejects.toThrow('Bad Request');
  });

  it('POST with no body sends undefined body', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    vi.stubGlobal('fetch', mockFetch);
    await api.post('/api/action');
    expect(mockFetch).toHaveBeenCalledWith('/api/action', expect.objectContaining({
      method: 'POST',
      body: undefined,
    }));
  });
});
