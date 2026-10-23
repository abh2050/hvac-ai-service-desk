import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { currentRun } from '../run';

type Stage = { stage: string; status: string; started: string; seconds?: number; model_cost_usd?: number };
type Run = { run_id: string; scenario_id: string; source_type: string; note: string;
  replay: { status: string | null }; detection: { operating_windows: number; rule_alarm_windows: number; model_alarm_windows: number };
  case: { case_id: string; route: string; gate: { reason?: string; disagreement?: boolean } } | null; stages: Stage[];
  work_order: { work_order_id: string; status: string; status_reason: string } | null;
  ground_truth_label: { fault_type: string; category: string; source: string } | null };

const LABEL: Record<string, string> = {
  LetWindowsLand: 'Collect detection windows', DecideDay: 'Day decision (rules first, then model)', 'DiagnoseNeeded?': 'Diagnose this case?',
  DiagnoseCase: 'Diagnosis with manual retrieval', VerifyAndDraft: 'Citation check and work order draft',
  'NeedsApproval?': 'Needs approval?', WaitForApproval: 'Waiting for manager approval', DispatchOrTools: 'Dispatch (OR-Tools on Fargate)',
  EscalateExpired: 'Approval expired: escalated', NoApprovalNeeded: 'Stopped before approval', NoDiagnosis: 'No diagnosis', Done: 'Done', Rejected: 'Rejected',
};

export default function Pipeline() {
  const runId = currentRun();
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!runId) return;
    let stop = false;
    const tick = () => api<Run>(`/runs/${runId}`).then((r) => { if (!stop) setRun(r); }).catch((e) => setError(e.message));
    tick();
    const id = window.setInterval(tick, 3000);
    return () => { stop = true; window.clearInterval(id); };
  }, [runId]);
  if (!runId) return <><h1>Live pipeline</h1><p>Start a replay from the <Link to="/scenarios">scenario launcher</Link>.</p></>;
  const cost = run?.stages.reduce((a, s) => a + (s.model_cost_usd ?? 0), 0) ?? 0;
  return (
    <>
      <h1>Live pipeline</h1>
      <p className="muted">Run <code>{runId}</code>, recorded day {run?.scenario_id}. Replay of recorded data.</p>
      {error && <div className="banner bad">{error}</div>}
      <div className="card row">
        <div><strong>Replay</strong><div>{run?.replay.status ?? 'starting'}</div></div>
        <div><strong>Operating hours</strong><div>{run?.detection.operating_windows ?? 0}</div></div>
        <div><strong>Rule alarms</strong><div>{run?.detection.rule_alarm_windows ?? 0}</div></div>
        <div><strong>Model alarms</strong><div>{run?.detection.model_alarm_windows ?? 0}</div></div>
        <div><strong>Model cost (this case)</strong><div>${cost.toFixed(4)}</div></div>
      </div>
      {run?.case?.gate?.disagreement && <div className="banner warn">The rules and the model disagree. A manager must review this case.</div>}
      {run?.case?.route === 'manual_review' && <div className="banner warn">Detection confidence is below the threshold. The case goes to manual review and is not diagnosed.</div>}
      {run?.case?.route === 'no_fault_detected' && <div className="banner ok">Fewer than two alarm hours. No case was opened.</div>}
      <div className="card">
        <table>
          <thead><tr><th>Stage</th><th>Status</th><th>Seconds</th><th>Model cost</th></tr></thead>
          <tbody>
            {(run?.stages ?? []).map((s, i) => (
              <tr key={i}><td>{LABEL[s.stage] ?? s.stage}</td>
                <td><span className={`pill ${s.status === 'done' ? 'ok' : s.status === 'running' ? 'warn' : 'bad'}`}>{s.status}</span></td>
                <td>{s.seconds ?? ''}</td><td>{s.model_cost_usd ? `$${s.model_cost_usd.toFixed(4)}` : ''}</td></tr>
            ))}
          </tbody>
        </table>
        {!run?.stages.length && <p className="muted">Waiting for the end of the replayed day.</p>}
      </div>
      {run?.work_order && (
        <div className={`banner ${run.work_order.status === 'blocked' ? 'bad' : 'ok'}`}>
          Work order {run.work_order.work_order_id}: {run.work_order.status}. {run.work_order.status_reason}
          {' '}<Link to="/work-orders">Open the queue</Link>
        </div>
      )}
      {run?.ground_truth_label && (
        <div className="card"><strong>Published label (ground truth): </strong>{run.ground_truth_label.fault_type.replace(/_/g, ' ')}
          {' '}<span className="muted">({run.ground_truth_label.category}; {run.ground_truth_label.source})</span></div>
      )}
      <div className="row"><Link to="/asset">Asset view</Link><Link to="/diagnosis">Diagnosis</Link><Link to="/dispatch">Dispatch board</Link></div>
    </>
  );
}
