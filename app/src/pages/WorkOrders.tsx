import { useEffect, useState } from 'react';
import { api, type Me } from '../api';
import { SNAPSHOT, STATIC } from '../mode';

type Step = { kind: string; seq: number; quote: string; manual_id: string; page: number };
type WO = { work_order_id: string; asset_id: string; status: string; status_reason: string; priority: string; sla_due_at: string;
  fault_type: string; route: string; required_certs: string[]; compatibility_uncertain: boolean; detection_disagreement: boolean; steps: Step[] };

export default function WorkOrders({ me }: { me: Me | null }) {
  const [items, setItems] = useState<WO[]>([]);
  const [error, setError] = useState('');
  const [keep, setKeep] = useState<Record<string, Set<number>>>({});
  const load = () => api<WO[]>('/work-orders').then(setItems).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function act(wo: WO, action: 'approve' | 'reject') {
    setError('');
    try {
      if (action === 'approve') {
        const k = keep[wo.work_order_id];
        await api(`/work-orders/${wo.work_order_id}/approve`, { method: 'POST',
          body: JSON.stringify(k ? { keep_step_indexes: [...k] } : {}) });
      } else {
        const reason = window.prompt('Reason for rejecting this work order?');
        if (!reason) return;
        await api(`/work-orders/${wo.work_order_id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) });
      }
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function toggle(woId: string, i: number, total: number) {
    setKeep((prev) => {
      const s = new Set(prev[woId] ?? Array.from({ length: total }, (_, j) => j));
      if (s.has(i)) s.delete(i); else s.add(i);
      return { ...prev, [woId]: s };
    });
  }

  return (
    <>
      <h1>Work orders</h1>
      <p className="muted">Every instruction is a verified quote from an equipment manual, with its page. The database refuses anything else.</p>
      {STATIC && <div className="banner warn">Recorded queue. The manager approved {SNAPSHOT?.work_order_id} in the live run, which resumed the
        pipeline and dispatched it. The other orders are the labeled scenario week used for the dispatch board. One of them is blocked:
        no lockout step could be sourced from a manual, so no one can approve it.</div>}
      {error && <div className="banner bad">{error}</div>}
      {items.length === 0 && <p>No work orders yet.</p>}
      {items.map((wo) => (
        <div className="card" key={wo.work_order_id}>
          <div className="row">
            <strong>{wo.work_order_id}</strong>
            <span className={`pill ${wo.status === 'blocked' ? 'bad' : wo.status === 'draft' ? 'warn' : 'ok'}`}>{wo.status}</span>
            <span className="pill">{wo.priority}</span>
            <span className="muted">{wo.asset_id}, {wo.fault_type.replace(/_/g, ' ')}, SLA due {wo.sla_due_at}</span>
          </div>
          {wo.status === 'blocked' && <div className="banner bad">Blocked: {wo.status_reason}</div>}
          {wo.compatibility_uncertain && <div className="banner warn">Compatibility uncertain: the manuals match the equipment class, not the exact model.</div>}
          {wo.detection_disagreement && <div className="banner warn">The rules and the model disagreed on detection.</div>}
          <p className="muted">Required certifications: {wo.required_certs.join(', ') || 'none'}. Route: {wo.route.replace(/_/g, ' ')}.</p>
          {wo.steps.map((s, i) => (
            <div key={i} className="row" style={{ alignItems: 'flex-start' }}>
              {me?.role === 'manager' && wo.status === 'draft' && (
                <input type="checkbox" aria-label="keep step" checked={keep[wo.work_order_id]?.has(i) ?? true}
                  onChange={() => toggle(wo.work_order_id, i, wo.steps.length)} />
              )}
              <div style={{ flex: 1 }}>
                <span className={`pill ${s.kind === 'safety' ? 'warn' : 'ok'}`}>{s.kind === 'safety' ? 'Safety step' : s.kind === 'check' ? 'Check' : 'Evidence'}</span>
                <span className="muted"> {s.manual_id}, page {s.page}</span>
                <blockquote>{s.quote}</blockquote>
              </div>
            </div>
          ))}
          {me?.role === 'manager' && (wo.status === 'draft' || wo.status === 'blocked') && (
            <div className="row">
              {wo.status === 'draft' && wo.route === 'technician' && <button onClick={() => act(wo, 'approve')}>Approve and dispatch</button>}
              <button className="secondary" onClick={() => act(wo, 'reject')}>Reject</button>
              {wo.status === 'draft' && <span className="muted">Untick a step to remove it. A manager cannot add free text, and cannot remove every safety step.</span>}
            </div>
          )}
        </div>
      ))}
    </>
  );
}
