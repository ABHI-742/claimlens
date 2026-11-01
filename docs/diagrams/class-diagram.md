# Class diagram (domain and services)

Names match the code in `backend/app/`.

```mermaid
classDiagram
    direction LR

    class Claim {
        +UUID id
        +str policy_number
        +ClaimStatus status
        +TriageQueue queue
        +float triage_score
        +str failure_reason
    }
    class Document {
        +str s3_key
        +str content_sha256
        +str ocr_text_masked
        +float ocr_confidence
    }
    class ClaimFactsRow
    class CoverageAssessmentRow
    class FraudFlagRow
    Claim "1" *-- "many" Document
    Claim "1" *-- "0..1" ClaimFactsRow
    Claim "1" *-- "0..1" CoverageAssessmentRow
    Claim "1" *-- "many" FraudFlagRow

    class Worker {
        +handle(job)
        +run_forever()
    }
    class JobQueue {
        <<interface>>
        +send(type, id)
        +receive() list
        +delete(job)
    }
    class SqsQueue
    JobQueue <|.. SqsQueue
    class Storage {
        <<interface>>
        +presign_put(key, mime)
        +presign_get(key)
        +get_bytes(key)
    }
    class S3Storage
    Storage <|.. S3Storage
    class PolicyIngestor {
        +ingest(policy_id)
    }
    Worker --> JobQueue
    Worker --> ClaimPipeline
    Worker --> PolicyIngestor

    class ClaimPipeline {
        +run(claim_id)
        +mark_failed(claim_id, reason)
    }
    class OcrProvider {
        <<interface>>
        +extract(data, mime) OcrResult
    }
    class TextractOcr
    class TesseractOcr
    OcrProvider <|.. TextractOcr
    OcrProvider <|.. TesseractOcr

    class PiiMasker {
        +mask(text) MaskedText
    }
    class StructuredLlm {
        <<interface>>
        +json(system, user, schema) dict
    }
    class ClaudeStructuredLlm {
        +str model
    }
    StructuredLlm <|.. ClaudeStructuredLlm

    class ClaimExtractor {
        <<interface>>
        +extract(masked_text, product) Extraction
    }
    class ClaudeClaimExtractor
    ClaimExtractor <|.. ClaudeClaimExtractor
    class CoverageAssessor {
        <<interface>>
        +assess(facts, clauses) CoverageAssessment
    }
    class ClaudeCoverageAssessor
    CoverageAssessor <|.. ClaudeCoverageAssessor
    ClaudeClaimExtractor --> StructuredLlm
    ClaudeCoverageAssessor --> StructuredLlm

    class PolicyRetriever {
        <<interface>>
        +top_k(query, product, k) list
    }
    class PgVectorRetriever
    PolicyRetriever <|.. PgVectorRetriever
    class EmbeddingProvider {
        <<interface>>
        +embed(texts) list
    }
    class HashEmbeddings
    class LocalModelEmbeddings
    class BedrockTitanEmbeddings
    EmbeddingProvider <|.. HashEmbeddings
    EmbeddingProvider <|.. LocalModelEmbeddings
    EmbeddingProvider <|.. BedrockTitanEmbeddings
    PgVectorRetriever --> EmbeddingProvider

    class FraudRuleEngine {
        +evaluate(ctx) list
    }
    class TriageScorer {
        +score(facts, coverage, flags) TriageResult
    }

    ClaimPipeline --> Storage
    ClaimPipeline --> OcrProvider
    ClaimPipeline --> PiiMasker
    ClaimPipeline --> ClaimExtractor
    ClaimPipeline --> PolicyRetriever
    ClaimPipeline --> CoverageAssessor
    ClaimPipeline --> FraudRuleEngine
    ClaimPipeline --> TriageScorer
    ClaimPipeline --> Claim
```

Every `<<interface>>` is a Python `Protocol`. `ClaudeStructuredLlm` calls `claude-opus-5-5` with JSON-schema structured outputs; `ClaudeCoverageAssessor` raises `CitationError` when a cited clause was not retrieved. The tests swap in fakes (`FakeStorage`, `FakeQueue`, `FakeLlm`) through the same interfaces.
