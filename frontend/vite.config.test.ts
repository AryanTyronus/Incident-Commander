import { describe, it, expect } from 'vitest';
import type { ProxyOptions, UserConfig } from 'vite';
import viteConfig from './vite.config.ts';

/**
 * The dev server proxies the browser's calls to FastAPI. The incident event
 * stream is a WebSocket, and Vite only forwards upgrade requests for a proxy
 * entry that opts in with `ws: true` - without it the Investigate flow's live
 * progress silently never arrives.
 */
const WS_PATH = '/api/incidents/00000000-0000-0000-0000-000000000000/stream';
const BACKEND = 'http://localhost:8000';

const config = viteConfig as UserConfig;
const proxy = (config.server?.proxy ?? {}) as Record<string, string | ProxyOptions>;

function entryFor(path: string): [string, ProxyOptions] {
  const prefix = Object.keys(proxy)
    .filter((key) => path.startsWith(key))
    .sort((a, b) => b.length - a.length)[0];
  expect(prefix, `no proxy entry matches ${path}`).toBeDefined();
  const options = proxy[prefix];
  expect(typeof options, `proxy entry ${prefix} must be an options object`).toBe('object');
  return [prefix, options as ProxyOptions];
}

describe('vite dev server proxy', () => {
  it('routes the API prefix to the backend', () => {
    const [, options] = entryFor('/api/incidents');
    expect(options.target).toBe(BACKEND);
  });

  it('forwards WebSocket upgrades on the prefix that serves the event stream', () => {
    const [prefix, options] = entryFor(WS_PATH);
    expect(prefix).toBe('/api');
    expect(options.ws).toBe(true);
  });

  it('has no unused /ws entry', () => {
    // Nothing in the app connects to /ws; the stream lives under /api.
    expect(Object.keys(proxy)).not.toContain('/ws');
  });

  it('still proxies the health probes', () => {
    expect(entryFor('/health')[1].target).toBe(BACKEND);
    expect(entryFor('/ready')[1].target).toBe(BACKEND);
  });
});
