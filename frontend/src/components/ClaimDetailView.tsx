import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type Decision } from '../api';

const ACTIONS: { decision: Decision; label: string; className?: string }[] = [
  { decision: 'APPROVE', label: 'Approve' },
  { decision: 'REQUEST_INFO', label: 'Request information', className: 'secondary' },
  { decision: 'ESCALATE', label: 'Escalate', className: 'secondary' },
  { decision: 'DENY', label: 'Deny', className: 'danger' },
];

export function ClaimDetailView({ id, onBack }: { id: string; onBack: () => void }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const { data: claim, error } = useQuery({
    queryKey: ['claim', id],
    queryFn: () => api.getClaim(id),
    // Poll while the pipeline is still running.
    refetchInterval: (query) =>
      ['SUBMITTED', 'PROCESSING'].includes(query.state.data?.status ?? '') ? 3000 : false,
  });
  const decide = useMutation({
    mutationFn: (decision: Decision) => api.decide(id, decision, note),
    onSuccess: (updated) => {
      queryClient.setQueryData(['claim', id], updated);
      queryClient.invalidateQueries({ queryKey: ['claims'] });
      setNote('');
    },
  });

  if (error) return <p className="error">{(error as Error).message}</p>;
  if (!claim) return <p className="muted">Loading…</p>;

  const openDocument = async (docId: string) => {
    const { url } = await api.documentUrl(id, docId);
    window.open(url, '_blank', 'noopener');
  };

  return (
    <section className="detail">
      <button type="button" className="link" onClick={onBack}>
        ← Back to queue
      </button>
      <h2>
        {claim.policy_number} <span className="muted">· {claim.product}</span>
      </h2>
      <p>
        <span className="pill">{claim.status.replaceAll('_', ' ')}</span>{' '}
        {claim.queue && <span className="pill">{claim.queue.replaceAll('_', ' ')}</span>}{' '}
        {claim.triage_score !== null && <span className="muted">score {claim.triage_score.toFixed(2)}</span>}
      </p>
      {claim.failure_reason && <p className="error">Processing failed: {claim.failure_reason}</p>}

      <div className="grid">
        <div className="card">
          <h3>Extracted facts</h3>
          {claim.facts ? (
            <dl>
              <dt>Loss date</dt>
              <dd>{claim.facts.loss_date ?? 'Not found'}</dd>
              <dt>Loss type</dt>
              <dd>{claim.facts.loss_type}</dd>
              <dt>Location</dt>
              <dd>{claim.facts.location ?? 'Not found'}</dd>
              <dt>Claimed</dt>
              <dd>{claim.facts.claimed_amount ?? 'Not found'}</dd>
              <dt>Severity</dt>
              <dd>{claim.severity?.toFixed(2)}</dd>
            </dl>
          ) : (
            <p className="muted">Waiting for the pipeline…</p>
          )}
          {claim.facts && <p>{claim.facts.description}</p>}
        </div>

        <div className="card">
          <h3>Coverage</h3>
          {claim.coverage ? (
            <>
              <p>
                <strong>{claim.coverage.verdict.replaceAll('_', ' ')}</strong>{' '}
                <span className="muted">(uncertainty {claim.coverage.uncertainty.toFixed(2)})</span>
              </p>
              <p>{claim.coverage.reasoning}</p>
              {claim.citations.map((c) => (
                <details key={c.clause_id}>
                  <summary>{c.clause_id}</summary>
                  <pre>{c.content}</pre>
                </details>
              ))}
            </>
          ) : (
            <p className="muted">Not assessed yet.</p>
          )}
        </div>

        <div className="card">
          <h3>Fraud signals</h3>
          {claim.fraud_flags.length === 0 && <p className="muted">None.</p>}
          <ul className="flags">
            {claim.fraud_flags.map((f, i) => (
              <li key={i}>
                <span className={`pill ${f.severity.toLowerCase()}`}>{f.severity}</span> <code>{f.code}</code>
                <div>{f.evidence}</div>
              </li>
            ))}
          </ul>
          {claim.inconsistencies.length > 0 && (
            <>
              <h4>Inconsistencies noted</h4>
              <ul>
                {claim.inconsistencies.map((text, i) => (
                  <li key={i}>{text}</li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="card">
          <h3>Documents</h3>
          <ul>
            {claim.documents.map((d) => (
              <li key={d.id}>
                <button type="button" className="link" onClick={() => openDocument(d.id)}>
                  {d.filename}
                </button>{' '}
                {d.ocr_confidence !== null && (
                  <span className="muted small">OCR {(d.ocr_confidence * 100).toFixed(0)}%</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {claim.status === 'READY_FOR_REVIEW' && (
        <div className="card">
          <h3>Decision</h3>
          <textarea
            placeholder="Note for the audit trail (required)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          {decide.error && <p className="error">{(decide.error as Error).message}</p>}
          <div className="actions">
            {ACTIONS.map((a) => (
              <button
                key={a.decision}
                type="button"
                className={a.className}
                disabled={!note.trim() || decide.isPending}
                onClick={() => decide.mutate(a.decision)}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <h3>Audit trail</h3>
        <ol className="audit">
          {claim.audit.map((e, i) => (
            <li key={i}>
              <span className="muted small">{new Date(e.at).toLocaleString()}</span> <code>{e.action}</code>{' '}
              <span className="muted small">{e.actor}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
