import { SNAPSHOT } from './mode';

// The current run is shared across pages through the URL (?run=) and local storage.
export function currentRun(): string | null {
  if (SNAPSHOT) return SNAPSHOT.run_id;     // the static demo holds one recorded run
  const fromUrl = new URLSearchParams(window.location.search).get('run');
  if (fromUrl) {
    try { localStorage.setItem('uptime-run', fromUrl); } catch { /* storage unavailable */ }
    return fromUrl;
  }
  try { return localStorage.getItem('uptime-run'); } catch { return null; }
}

export function rememberRun(runId: string) {
  try { localStorage.setItem('uptime-run', runId); } catch { /* storage unavailable */ }
}
