import { type FormEvent, useState } from 'react';
import { api } from '../api';

export function LoginForm({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState('adjuster@claimlens.dev');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.login(email, password);
      onLogin();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    }
  }

  return (
    <form className="card login" onSubmit={submit}>
      <h1>ClaimLens</h1>
      <p className="muted">Adjuster console</p>
      <label>
        Email
        <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit">Log in</button>
      <p className="muted small">Local seed users are listed in the README.</p>
    </form>
  );
}
