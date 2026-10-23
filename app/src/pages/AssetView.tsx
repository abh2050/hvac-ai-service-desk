import { useEffect, useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import { currentRun } from '../run';

type Win = { window_start: string; rule_alarm: boolean; model_alarm: boolean; model_prob: number; rules_fired: string; rule_hint: string | null };
type Trend = { scenario_id: string; columns: string[]; series: Record<string, number | string>[]; windows: Win[]; note: string };
const COLORS = ['#0b6e66', '#b5651d', '#5a4fcf', '#a3262a', '#2f7d32'];

export default function AssetView() {
  const runId = currentRun();
  const [t, setT] = useState<Trend | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { if (runId) api<Trend>(`/runs/${runId}/trend`).then(setT).catch((e) => setError(e.message)); }, [runId]);
  if (!runId) return <><h1>Asset view</h1><p>Start a replay first.</p></>;
  const hhmm = (s: string) => s.slice(11, 16);
  return (
    <>
      <h1>Asset view</h1>
      <p className="muted">Recorded day {t?.scenario_id}. Replay of recorded data. Shaded hours are alarm windows: orange when the rules fired, purple when only the model alarmed.</p>
      {error && <div className="banner bad">{error}</div>}
      <div className="card" style={{ height: 380 }}>
        <ResponsiveContainer>
          <LineChart data={t?.series ?? []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="t" tickFormatter={hhmm} minTickGap={24} />
            <YAxis />
            <Tooltip labelFormatter={(v) => String(v)} />
            <Legend />
            {(t?.windows ?? []).filter((w) => w.rule_alarm || w.model_alarm).map((w) => {
              const start = w.window_start.replace(' ', 'T').slice(0, 16).replace('T', ' ');
              const x1 = (t?.series ?? []).find((p) => String(p.t).startsWith(start.slice(0, 13)))?.t;
              const x2 = [...(t?.series ?? [])].reverse().find((p) => String(p.t).startsWith(start.slice(0, 13)))?.t;
              return x1 && x2 ? <ReferenceArea key={w.window_start} x1={x1} x2={x2} fill={w.rule_alarm ? '#f0a23b' : '#8f7fe8'} fillOpacity={0.25} /> : null;
            })}
            {(t?.columns ?? []).map((c, i) => <Line key={c} dataKey={c} dot={false} stroke={COLORS[i % COLORS.length]} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h2>Rules baseline next to the model, per hour</h2>
        <table>
          <thead><tr><th>Hour</th><th>Rules</th><th>Rules fired</th><th>Model probability</th><th>Model</th></tr></thead>
          <tbody>
            {(t?.windows ?? []).map((w) => (
              <tr key={w.window_start}><td>{hhmm(w.window_start)}</td>
                <td><span className={`pill ${w.rule_alarm ? 'bad' : 'ok'}`}>{w.rule_alarm ? 'alarm' : 'normal'}</span></td>
                <td>{w.rules_fired || ''}{w.rule_hint ? ` (points to ${w.rule_hint.replace(/_/g, ' ')})` : ''}</td>
                <td>{w.model_prob?.toFixed(2)}</td>
                <td><span className={`pill ${w.model_alarm ? 'bad' : 'ok'}`}>{w.model_alarm ? 'alarm' : 'normal'}</span></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
