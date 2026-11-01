const queues = [
  { id: 'FAST_TRACK', label: 'Fast-track' },
  { id: 'STANDARD', label: 'Standard review' },
  { id: 'INVESTIGATE', label: 'Investigate' },
];

// Roadmap: queue list, claim detail with evidence viewer, decision actions.
export default function App() {
  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: 24 }}>
      <h1>ClaimLens</h1>
      <p>Adjuster console</p>
      <nav>
        {queues.map((q) => (
          <button key={q.id} type="button" style={{ marginRight: 8 }}>
            {q.label}
          </button>
        ))}
      </nav>
    </main>
  );
}
