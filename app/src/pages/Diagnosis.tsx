import { useEffect, useState } from 'react';
import { api } from '../api';
import { currentRun } from '../run';
import { STATIC } from '../mode';

type Cite = { kind: string; manual_id: string; page: number; quote: string; claim?: string; url: string; support: string };
type Diag = { ready: boolean; probable_cause?: string; llm_proposed_cause?: string; confidence?: number; explanation?: string;
  abstained?: boolean; route?: string; compatibility_uncertain?: boolean; lockout_sourced?: boolean; citations?: Cite[];
  removed_unverified?: Record<string, number>; rules_vs_model?: { rules_alarm_windows: number; model_alarm_windows: number; disagreement: boolean } };

const KIND = { citation: 'Evidence', check: 'Check', safety: 'Safety step' } as const;

export default function Diagnosis() {
  const runId = currentRun();
  const [d, setD] = useState<Diag | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!runId) return;
    let stop = false;
    const tick = () => api<Diag>(`/runs/${runId}/diagnosis`).then((x) => { if (!stop) setD(x); }).catch((e) => setError(e.message));
    tick();
    if (STATIC) return;
    const id = window.setInterval(tick, 4000);
    return () => { stop = true; window.clearInterval(id); };
  }, [runId]);
  if (!runId) return <><h1>Diagnosis</h1><p>Start a replay first.</p></>;
  if (!d?.ready) return <><h1>Diagnosis</h1>{error ? <div className="banner bad">{error}</div> : <p className="muted">Waiting for the diagnosis step.</p>}</>;
  const removed = Object.values(d.removed_unverified ?? {}).reduce((a, b) => a + b, 0);
  return (
    <>
      <h1>Diagnosis</h1>
      {d.abstained && <div className="banner bad">Insufficient evidence. No manual passage supported the cause, so nothing is shown as fact. The case goes to manual review.</div>}
      {d.route === 'operations_review' && <div className="banner warn">Building operations issue. It goes to operations review, and no technician is dispatched.</div>}
      {d.compatibility_uncertain && <div className="banner warn">Compatibility uncertain. The cited manuals cover this equipment class but not this exact model.</div>}
      {d.rules_vs_model?.disagreement && <div className="banner warn">The rules ({d.rules_vs_model.rules_alarm_windows} alarm hours) and the model ({d.rules_vs_model.model_alarm_windows} alarm hours) disagree. A manager must review.</div>}
      <div className="card">
        <div className="row">
          <div><strong>Probable cause</strong><div>{(d.probable_cause ?? '').replace(/_/g, ' ')}</div></div>
          {d.abstained && d.llm_proposed_cause && <div><strong>Proposed, not verified</strong><div className="muted">{d.llm_proposed_cause.replace(/_/g, ' ')}</div></div>}
          <div><strong>Model confidence</strong><div>{d.confidence != null ? Number(d.confidence).toFixed(2) : 'n/a'}</div></div>
          <div><strong>Lockout step sourced</strong><div>{d.lockout_sourced ? 'yes' : 'no'}</div></div>
        </div>
        {d.explanation && <p className="muted">{d.explanation}</p>}
      </div>
      <div className="card">
        <h2>Manual citations</h2>
        <p className="muted">Every quote below appears word for word on the cited page, and a second model confirmed that the page supports it.
          {removed > 0 && ` ${removed} unverified item${removed > 1 ? 's were' : ' was'} removed before display.`}</p>
        {(d.citations ?? []).length === 0 && <p>No verified citation.</p>}
        {(d.citations ?? []).map((c, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <span className={`pill ${c.kind === 'safety' ? 'warn' : 'ok'}`}>{KIND[c.kind as keyof typeof KIND]}</span>{' '}
            {c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.manual_id}, page {c.page}</a> : <span>{c.manual_id}, page {c.page}</span>}{' '}
            <span className="pill ok">{c.support}</span>
            <blockquote>{c.quote}</blockquote>
          </div>
        ))}
      </div>
    </>
  );
}
