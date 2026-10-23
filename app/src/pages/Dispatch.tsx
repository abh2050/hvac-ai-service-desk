import { useEffect, useState } from 'react';
import { api } from '../api';
import { SNAPSHOT } from '../mode';

type Item = { work_order_id: string; technician_id: string | null; runner_up_id: string | null; start_at: string | null;
  travel_minutes: number | null; lateness_minutes: number | null; reason: string; status: string; sla_due_at: string;
  priority: string; fault_type: string; asset_id: string; scenario_id: string | null };

function slaClock(due: string, now: number) {
  const ms = new Date(due.replace(' ', 'T')).getTime() - now;
  const h = Math.floor(Math.abs(ms) / 3.6e6), m = Math.floor((Math.abs(ms) % 3.6e6) / 6e4);
  return ms >= 0 ? `${h}h ${m}m left` : `${h}h ${m}m overdue`;
}

export default function Dispatch() {
  const [d, setD] = useState<{ assigned: Item[]; escalated: Item[]; note: string } | null>(null);
  const [error, setError] = useState('');
  // The static demo measures SLA clocks at capture time; a live clock would show every order overdue.
  const [now, setNow] = useState(SNAPSHOT ? new Date(SNAPSHOT.captured_at).getTime() : Date.now());
  useEffect(() => {
    api<typeof d>('/dispatch').then(setD).catch((e) => setError(e.message));
    if (SNAPSHOT) return;
    const id = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <>
      <h1>Dispatch board</h1>
      <p className="muted">OR-Tools assigns approved work orders under hard constraints: certifications, shifts, site access, and escort clearance.
        Rows from the scenario week are scenario model results, not field savings.
        {SNAPSHOT && ` SLA clocks are as of capture, ${SNAPSHOT.captured_at.replace('T', ' ').slice(0, 16)} UTC.`}</p>
      {error && <div className="banner bad">{error}</div>}
      <div className="card">
        <h2>Assigned</h2>
        <table>
          <thead><tr><th>Work order</th><th>Technician</th><th>Runner-up</th><th>Start</th><th>Travel</th><th>SLA clock</th><th>Reason</th></tr></thead>
          <tbody>
            {(d?.assigned ?? []).map((i) => (
              <tr key={i.work_order_id}>
                <td>{i.work_order_id}<div className="muted">{i.priority}, {i.fault_type.replace(/_/g, ' ')}{i.scenario_id ? ', scenario' : ''}</div></td>
                <td>{i.technician_id}</td><td>{i.runner_up_id ?? 'none'}</td><td>{i.start_at}</td>
                <td>{i.travel_minutes != null ? `${Math.round(i.travel_minutes)} min` : ''}</td>
                <td><span className={`pill ${new Date(i.sla_due_at.replace(' ', 'T')).getTime() < now ? 'bad' : 'ok'}`}>{slaClock(i.sla_due_at, now)}</span></td>
                <td>{i.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>Escalated or waiting to reschedule</h2>
        {(d?.escalated ?? []).length === 0 && <p className="muted">None.</p>}
        <table>
          <tbody>
            {(d?.escalated ?? []).map((i) => (
              <tr key={i.work_order_id}><td>{i.work_order_id}</td><td><span className="pill bad">{i.status.replace(/_/g, ' ')}</span></td><td>{i.reason}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
