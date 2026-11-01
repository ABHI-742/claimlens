import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type Queue } from '../api';

const QUEUES: { id: Queue; label: string; hint: string }[] = [
  { id: 'FAST_TRACK', label: 'Fast-track', hint: 'Small, covered, no fraud signals' },
  { id: 'STANDARD', label: 'Standard review', hint: 'Needs a normal review' },
  { id: 'INVESTIGATE', label: 'Investigate', hint: 'High risk or fraud signals' },
];

const money = (value: string | null) =>
  value === null ? '—' : Number(value).toLocaleString(undefined, { style: 'currency', currency: 'USD' });

export function ClaimQueue({ onOpen }: { onOpen: (id: string) => void }) {
  const [queue, setQueue] = useState<Queue>('STANDARD');
  const { data, isLoading, error } = useQuery({
    queryKey: ['claims', queue],
    queryFn: () => api.listClaims(queue),
    refetchInterval: 10_000,
  });

  return (
    <section>
      <nav className="tabs">
        {QUEUES.map((q) => (
          <button
            key={q.id}
            type="button"
            className={q.id === queue ? 'tab active' : 'tab'}
            onClick={() => setQueue(q.id)}
            title={q.hint}
          >
            {q.label}
          </button>
        ))}
      </nav>
      {isLoading && <p className="muted">Loading…</p>}
      {error && <p className="error">{(error as Error).message}</p>}
      {data && data.length === 0 && <p className="muted">No claims waiting in this queue.</p>}
      {data && data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Policy</th>
              <th>Product</th>
              <th>Claimed</th>
              <th>Score</th>
              <th>Flags</th>
              <th>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {data.map((c) => (
              <tr key={c.id} onClick={() => onOpen(c.id)} className="clickable">
                <td>{c.policy_number}</td>
                <td>{c.product}</td>
                <td>{money(c.claimed_amount)}</td>
                <td>{c.triage_score?.toFixed(2) ?? '—'}</td>
                <td>{c.flag_count > 0 ? <span className="pill warn">{c.flag_count}</span> : '—'}</td>
                <td>{c.submitted_at ? new Date(c.submitted_at).toLocaleString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
