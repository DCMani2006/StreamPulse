/**
 * StreamPulse Dynamic API & WebSocket Endpoint Resolver
 * Automatically resolves endpoint URLs for Localhost, Vercel, and Cloud deployments.
 */

export function getBackendApiUrl(): string {
  // 1. Check custom user-configured backend in localStorage
  if (typeof window !== 'undefined') {
    try {
      const custom = localStorage.getItem('streampulse_backend_api_url');
      if (custom && custom.trim()) {
        return custom.trim().replace(/\/+$/, '');
      }
    } catch {
      // Ignore localStorage errors
    }
  }

  // 2. Check Vite environment variable
  const metaEnv = (import.meta as any).env;
  if (metaEnv && metaEnv.VITE_API_URL) {
    return String(metaEnv.VITE_API_URL).replace(/\/+$/, '');
  }

  // 3. If running locally on localhost or 127.0.0.1
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0') {
      return `http://${host}:8000`;
    }
  }

  // 4. Default fallback for local backend
  return 'http://localhost:8000';
}

export function getBackendWsUrl(streamId: string, type: 'ingest' | 'telemetry'): string {
  // 1. Check custom user-configured WS URL
  if (typeof window !== 'undefined') {
    try {
      const custom = localStorage.getItem('streampulse_backend_ws_url');
      if (custom && custom.trim()) {
        const base = custom.trim().replace(/\/+$/, '');
        return `${base}/ws/${type}/${streamId}`;
      }
    } catch {
      // Ignore
    }
  }

  // 2. Check Vite environment variable
  const metaEnv = (import.meta as any).env;
  if (metaEnv && metaEnv.VITE_WS_URL) {
    const base = String(metaEnv.VITE_WS_URL).replace(/\/+$/, '');
    return `${base}/ws/${type}/${streamId}`;
  }

  // 3. Derive from API URL
  const apiUrl = getBackendApiUrl();
  const wsBase = apiUrl.replace(/^http:/i, 'ws:').replace(/^https:/i, 'wss:');
  return `${wsBase}/ws/${type}/${streamId}`;
}
