import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type Me } from '../api';
import { rememberRun } from '../run';

type Scenario = { scenario_id: string; source_type: 'lab' | 'field'; family: string; unit: string; asset_id: string;
  site_id: string; equipment_class: string; day: string; operating_windows: number };

const FAMILY = { ahu: 'Air handler', econ: 'Rooftop unit, economizer', refrig: 'Rooftop unit, refrigerant circuits' } as const;

export default function Scenarios({ me }: { me: Me | null }) {
  const [items, setItems] = useState<Scenario[]>([]);
  const [source, setSource] = useState<'all' | 'lab' | 'field'>('all');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const nav = useNavigate();
  useEffect(() => { api<Scenario[]>('/scenarios').then(setItems).catch((e) => setError(e.message)); }, []);
  const shown = useMemo(() => items.filter((s) => source === 'all' || s.source_type === source), [items, source]);

  async function start(id: string) {
    setBusy(id);
    setError('');
    try {
      const r = await api<{ run_id: string }>('/runs', { method: 'POST', body: JSON.stringify({ scenario_id: id, hours_per_second: 4 }) });
      rememberRun(r.run_id);
      nav(`/pipeline?run=${r.run_id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }

  return (
    <>
      <h1>Scenario launcher</h1>
      <p className="muted">Each scenario replays one recorded operating day from the LBNL fault datasets through the live pipeline.
        The replay keeps the original timestamps. The published fault label appears after the run finishes.</p>
      <div className="banner ok">Replay of recorded data. No reading on this page is simulated.</div>
      <div className="row" style={{ margin: '12px 0' }}>
        <label>Source{' '}
          <select value={source} onChange={(e) => setSource(e.target.value as typeof source)}>
            <option value="all">Lab and field</option><option value="lab">Lab tests</option><option value="field">Field measured</option>
          </select>
        </label>
        <span className="muted">{shown.length} recorded days</span>
      </div>
      {error && <div className="banner bad">{error}</div>}
      {me?.role !== 'manager' && <div className="banner warn">Only a manager can start a replay.</div>}
      <div className="card">
        <table>
          <thead><tr><th>Recorded day</th><th>Source</th><th>Equipment</th><th>Asset</th><th>Operating hours</th><th></th></tr></thead>
          <tbody>
            {shown.map((s) => (
              <tr key={s.scenario_id}>
                <td>{s.day}<div className="muted"><code>{s.unit}</code></div></td>
                <td><span className={`pill ${s.source_type}`}>{s.source_type === 'lab' ? 'Lab test' : 'Field measured'}</span></td>
                <td>{FAMILY[s.family as keyof typeof FAMILY] ?? s.family}</td>
                <td>{s.asset_id}<div className="muted">{s.site_id}</div></td>
                <td>{s.operating_windows}</td>
                <td><button disabled={me?.role !== 'manager' || !!busy} onClick={() => start(s.scenario_id)}>
                  {busy === s.scenario_id ? 'Starting' : 'Replay'}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
