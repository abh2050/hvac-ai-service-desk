import { useEffect, useState } from 'react';
import { api, type Me } from '../api';

type Answer = { question: string; answer: string; citations_shown: { manual_id: string; page: number; quote: string }[];
  insufficient_evidence: boolean; answer_rewritten: boolean; tool_trace: { tool: string; input: Record<string, unknown>; error: boolean; denied: boolean }[];
  seconds: number; cost_usd: number };

// The model writes light markdown (**bold**). Render bold, show everything else as plain text.
function Rich({ text }: { text: string }) {
  return <>{text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <span key={i}>{part}</span>)}</>;
}

export default function Assistant() {
  const [q, setQ] = useState('What jobs do I have this week?');
  const [log, setLog] = useState<Answer[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => { api<Me>('/me').then(setMe).catch(() => undefined); }, []);
  async function ask() {
    setBusy(true);
    setError('');
    try {
      const a = await api<Answer>('/assistant', { method: 'POST', body: JSON.stringify({ question: q }) });
      setLog((l) => [a, ...l]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>Technician assistant</h1>
      <p className="muted">Ask about your own jobs. The assistant reads only your work orders and their assets. It quotes the manuals word for word and shows each tool call it made.</p>
      {me?.role === 'manager' && (
        <div className="banner warn">You are signed in as a manager. Managers have no jobs of their own: ask about any work order
          or asset by its id, for example a work order id from the Work orders page. Sign in as a technician to ask "what are my jobs".</div>
      )}
      <div className="card row">
        <input style={{ flex: 1, minWidth: 240 }} value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !busy) ask(); }} aria-label="Question" />
        <button disabled={busy || !q.trim()} onClick={ask}>{busy ? 'Thinking' : 'Ask'}</button>
      </div>
      {error && <div className="banner bad">{error}</div>}
      {log.map((a, i) => (
        <div className="card" key={i}>
          <p><strong>{a.question}</strong></p>
          {a.tool_trace.some((t) => t.denied) && <div className="banner bad">Access denied. That item belongs to another technician, and the request was recorded in the audit log.</div>}
          {a.insufficient_evidence && <div className="banner warn">The tools did not provide what this question needs.</div>}
          {a.answer_rewritten && <div className="banner warn">The answer restated manual steps in its own words, so only the verified quotes are shown.</div>}
          <p style={{ whiteSpace: 'pre-wrap' }}><Rich text={a.answer} /></p>
          {a.citations_shown.map((c, j) => (
            <div key={j}><span className="muted">{c.manual_id}, page {c.page}</span><blockquote>{c.quote}</blockquote></div>
          ))}
          <details><summary className="muted">Tool calls ({a.tool_trace.length}), {a.seconds}s, ${a.cost_usd.toFixed(4)}</summary>
            <ul>{a.tool_trace.map((t, j) => (
              <li key={j}><code>{t.tool}({JSON.stringify(t.input)})</code> {t.denied ? 'denied' : t.error ? 'failed' : 'ok'}</li>
            ))}</ul>
          </details>
        </div>
      ))}
    </>
  );
}
