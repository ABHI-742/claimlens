# Entity-relationship diagram

Mirrors `backend/app/db/models.py`.

```mermaid
erDiagram
    TEAMS ||--o{ USERS : has
    TEAMS ||--o{ CLAIMS : owns
    USERS ||--o{ REFRESH_TOKENS : "signed in with"
    USERS ||--o{ CLAIMS : "assigned"
    CLAIMS ||--|{ DOCUMENTS : contains
    CLAIMS ||--o| CLAIM_FACTS : "extracted into"
    CLAIMS ||--o| COVERAGE_ASSESSMENTS : "assessed by"
    CLAIMS ||--o{ FRAUD_FLAGS : raises
    CLAIMS ||--o{ AUDIT_EVENTS : logs
    POLICY_DOCUMENTS ||--|{ POLICY_CHUNKS : "split into"

    TEAMS {
        uuid id PK
        string name UK
    }
    USERS {
        uuid id PK
        string email UK
        string password_hash "PBKDF2-SHA256"
        string role "ADJUSTER, SUPERVISOR, ADMIN"
        uuid team_id FK
    }
    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        string token_hash UK "SHA-256, never the raw token"
        timestamptz expires_at
        timestamptz revoked_at "set on use, logout or reuse"
        timestamptz created_at
    }
    CLAIMS {
        uuid id PK
        string policy_number
        string product
        string status
        string queue "FAST_TRACK, STANDARD, INVESTIGATE"
        float triage_score
        uuid team_id FK
        uuid assignee_id FK
        timestamptz submitted_at
        text failure_reason
    }
    DOCUMENTS {
        uuid id PK
        uuid claim_id FK
        string filename
        string s3_key
        string mime_type
        string content_sha256 "duplicate detection"
        text ocr_text_masked "PII already masked"
        float ocr_confidence
    }
    CLAIM_FACTS {
        uuid claim_id PK
        date loss_date
        string loss_type
        string location
        numeric claimed_amount
        text description
        float severity
        json inconsistencies
    }
    COVERAGE_ASSESSMENTS {
        uuid claim_id PK
        string verdict "COVERED, NOT_COVERED, UNCLEAR"
        text reasoning
        float uncertainty
        json cited_clause_ids
        string model
    }
    FRAUD_FLAGS {
        uuid id PK
        uuid claim_id FK
        string code
        string severity
        text evidence
    }
    POLICY_DOCUMENTS {
        uuid id PK
        string product
        string version
        string s3_key
        string status
    }
    POLICY_CHUNKS {
        uuid id PK
        uuid policy_document_id FK
        string product
        string clause_id
        text content
        vector embedding
    }
    AUDIT_EVENTS {
        bigint id PK
        uuid claim_id FK
        string actor
        string action
        json before
        json after
        timestamptz at
    }
```

`POLICY_CHUNKS.embedding` is `vector(1024)` with an HNSW index (`vector_cosine_ops`). `AUDIT_EVENTS` is append-only: the application never updates or deletes rows.
