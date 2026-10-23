import { useEffect, useState } from 'react';

type Gate = { file: string; title: string; data: Record<string, unknown> | null };
const GATES: [string, string][] = [
  ['gate-0.json', 'Gate 0: setup'], ['gate-1.json', 'Gate 1: detection'], ['gate-2.json', 'Gate 2: diagnosis (test cases)'],
  ['gate-2-holdout.json', 'Gate 2: diagnosis (holdout)'], ['gate-2-stats.json', 'Gate 2: statistics'],
  ['gate-3.json', 'Gate 3: work orders and dispatch'], ['gate-4.json', 'Gate 4: technician assistant'], ['gate-5.json', 'Gate 5: cloud and app'],
];

export default function Evidence() {
  const [gates, setGates] = useState<Gate[]>([]);
  useEffect(() => {
    Promise.all(GATES.map(async ([file, title]) => {
      try {
        const r = await fetch(`/reports/${file}`);
        return { file, title, data: r.ok ? await r.json() : null };
      } catch {
        return { file, title, data: null };
      }
    })).then(setGates);
  }, []);
  return (
    <>
      <h1>Evidence</h1>
      <p className="muted">Every number in this app comes from a recorded run saved in the repository. Each scorecard links to its source JSON.</p>
      <div className="card">
        <p><span className="pill ok">Ground truth</span> The published LBNL fault labels.</p>
        <p><span className="pill">Measured</span> Detection accuracy, citation support, latency, cost, and computed optimizer results.</p>
        <p><span className="pill warn">Not validated</span> Downtime avoided, field visits saved, and dollar savings. This project claims none of these.</p>
        <p className="muted">Lab, field, and simulated results are reported separately. Dispatch numbers are scenario model results.</p>
      </div>
      {gates.map((g) => (
        <div className="card" key={g.file}>
          <div className="row"><h2 style={{ margin: 0 }}>{g.title}</h2>
            <a href={`/reports/${g.file}`} target="_blank" rel="noreferrer">source JSON</a>
            <a href={`/reports/${g.file.replace('.json', '.md')}`} target="_blank" rel="noreferrer">report</a></div>
          {g.data ? <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 260, overflow: 'auto' }}>
            {JSON.stringify((g.data as Record<string, unknown>).summary ?? (g.data as Record<string, unknown>).results ?? g.data, null, 1).slice(0, 4000)}
          </pre> : <p className="muted">Not available.</p>}
        </div>
      ))}
    </>
  );
}
