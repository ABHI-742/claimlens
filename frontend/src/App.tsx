import { useEffect, useState } from 'react';
import { api } from './api';
import { ClaimDetailView } from './components/ClaimDetailView';
import { ClaimQueue } from './components/ClaimQueue';
import { LoginForm } from './components/LoginForm';
import { NewClaimForm } from './components/NewClaimForm';
import './styles.css';

type View = { kind: 'queue' } | { kind: 'claim'; id: string } | { kind: 'new' };

export default function App() {
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);
  const [view, setView] = useState<View>({ kind: 'queue' });

  useEffect(() => {
    api.restoreSession().then(setLoggedIn);
  }, []);

  if (loggedIn === null) return <p className="muted">Loading…</p>;
  if (!loggedIn) return <LoginForm onLogin={() => setLoggedIn(true)} />;

  return (
    <div className="app">
      <header className="topbar">
        <button type="button" className="brand" onClick={() => setView({ kind: 'queue' })}>
          ClaimLens
        </button>
        <span className="muted">{api.role()?.toLowerCase()}</span>
        <div className="spacer" />
        <button type="button" onClick={() => setView({ kind: 'new' })}>
          New claim
        </button>
        <button
          type="button"
          className="secondary"
          onClick={async () => {
            await api.logout();
            setLoggedIn(false);
          }}
        >
          Log out
        </button>
      </header>
      <main>
        {view.kind === 'queue' && <ClaimQueue onOpen={(id) => setView({ kind: 'claim', id })} />}
        {view.kind === 'claim' && (
          <ClaimDetailView id={view.id} onBack={() => setView({ kind: 'queue' })} />
        )}
        {view.kind === 'new' && (
          <NewClaimForm onSubmitted={(id) => setView({ kind: 'claim', id })} />
        )}
      </main>
    </div>
  );
}
