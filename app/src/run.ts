// The current run is shared across pages through the URL (?run=) and local storage.
export function currentRun(): string | null {
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
