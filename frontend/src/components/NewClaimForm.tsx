import { type FormEvent, useState } from 'react';
import { api } from '../api';

export function NewClaimForm({ onSubmitted }: { onSubmitted: (claimId: string) => void }) {
  const [policyNumber, setPolicyNumber] = useState('');
  const [product, setProduct] = useState('HO3');
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSubmitted(await api.submitClaim(policyNumber, product, files));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submission failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card narrow" onSubmit={submit}>
      <h2>New claim</h2>
      <label>
        Policy number
        <input value={policyNumber} onChange={(e) => setPolicyNumber(e.target.value)} required minLength={4} />
      </label>
      <label>
        Product
        <input value={product} onChange={(e) => setProduct(e.target.value)} required />
      </label>
      <label>
        Documents (PDF, images or text)
        <input
          type="file"
          multiple
          accept="application/pdf,image/png,image/jpeg,image/tiff,text/plain"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          required
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={busy || files.length === 0}>
        {busy ? 'Uploading…' : 'Submit claim'}
      </button>
    </form>
  );
}
