export type Queue = 'FAST_TRACK' | 'STANDARD' | 'INVESTIGATE';
export type Decision = 'APPROVE' | 'REQUEST_INFO' | 'ESCALATE' | 'DENY';

export interface ClaimSummary {
  id: string;
  policy_number: string;
  product: string;
  status: string;
  queue: Queue | null;
  triage_score: number | null;
  submitted_at: string | null;
  claimed_amount: string | null;
  flag_count: number;
}

export interface ClaimDetail extends ClaimSummary {
  severity: number | null;
  failure_reason: string | null;
  facts: {
    loss_date: string | null;
    loss_type: string;
    location: string | null;
    claimed_amount: string | null;
    description: string;
  } | null;
  inconsistencies: string[];
  coverage: { verdict: string; reasoning: string; cited_clause_ids: string[]; uncertainty: number } | null;
  citations: { clause_id: string; content: string }[];
  fraud_flags: { code: string; severity: 'LOW' | 'MEDIUM' | 'HIGH'; evidence: string }[];
  documents: { id: string; filename: string; mime_type: string; ocr_confidence: number | null }[];
  audit: { actor: string; action: string; after: Record<string, unknown> | null; at: string }[];
}

const BASE = '/api/v1';
let token: string | null = sessionStorage.getItem('claimlens.token');

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(BASE + path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === 'string' ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  isLoggedIn: () => token !== null,

  async login(email: string, password: string): Promise<string> {
    const result = await request<{ access_token: string; role: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    token = result.access_token;
    sessionStorage.setItem('claimlens.token', token);
    sessionStorage.setItem('claimlens.role', result.role);
    return result.role;
  },

  logout() {
    token = null;
    sessionStorage.removeItem('claimlens.token');
    sessionStorage.removeItem('claimlens.role');
  },

  role: () => sessionStorage.getItem('claimlens.role'),

  listClaims: (queue: Queue) =>
    request<ClaimSummary[]>(`/claims?queue=${queue}&status=READY_FOR_REVIEW`),

  getClaim: (id: string) => request<ClaimDetail>(`/claims/${id}`),

  documentUrl: (claimId: string, docId: string) =>
    request<{ url: string }>(`/claims/${claimId}/documents/${docId}/url`),

  decide: (id: string, decision: Decision, note: string) =>
    request<ClaimDetail>(`/claims/${id}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, note }),
    }),

  async submitClaim(policyNumber: string, product: string, files: File[]): Promise<string> {
    const created = await request<{
      claim_id: string;
      uploads: { document_id: string; filename: string; upload_url: string }[];
    }>('/claims', {
      method: 'POST',
      body: JSON.stringify({
        policy_number: policyNumber,
        product,
        documents: files.map((f) => ({ filename: f.name, mime_type: f.type || 'application/octet-stream' })),
      }),
    });
    await Promise.all(
      created.uploads.map((upload, i) =>
        fetch(upload.upload_url, {
          method: 'PUT',
          body: files[i],
          headers: { 'Content-Type': files[i].type },
        }).then((r) => {
          if (!r.ok) throw new ApiError(r.status, `Upload of ${upload.filename} failed`);
        }),
      ),
    );
    await request(`/claims/${created.claim_id}/submit`, { method: 'POST' });
    return created.claim_id;
  },
};
