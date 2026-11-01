# Class diagram (domain and services)

```mermaid
classDiagram
    direction LR

    class Claim {
        +UUID id
        +str policy_number
        +ClaimStatus status
        +TriageQueue queue
        +float triage_score
        +datetime submitted_at
        +submit()
        +mark_ready(result)
        +decide(decision, actor)
    }
    class Document {
        +UUID id
        +str s3_key
        +str mime_type
        +str ocr_text_masked
        +float ocr_confidence
    }
    class ClaimFacts {
        +date loss_date
        +str loss_type
        +str location
        +Decimal claimed_amount
        +str description
    }
    class CoverageAssessment {
        +CoverageVerdict verdict
        +str reasoning
        +list cited_clause_ids
        +float uncertainty
    }
    class FraudFlag {
        +str code
        +Severity severity
        +str evidence
    }

    Claim "1" *-- "many" Document
    Claim "1" *-- "0..1" ClaimFacts
    Claim "1" *-- "0..1" CoverageAssessment
    Claim "1" *-- "many" FraudFlag

    class OcrProvider {
        <<interface>>
        +extract(data, mime) OcrResult
    }
    class TextractOcr
    class TesseractOcr
    OcrProvider <|.. TextractOcr
    OcrProvider <|.. TesseractOcr

    class EmbeddingProvider {
        <<interface>>
        +embed(texts) list
    }
    class BedrockTitanEmbeddings
    class LocalEmbeddings
    EmbeddingProvider <|.. BedrockTitanEmbeddings
    EmbeddingProvider <|.. LocalEmbeddings

    class PiiMasker {
        +mask(text) MaskedText
    }
    class ClaimExtractor {
        +extract(masked_text) ClaimFacts
    }
    class PolicyRetriever {
        +top_k(query, product, k) list
    }
    class CoverageAssessor {
        +assess(facts, clauses) CoverageAssessment
    }
    class FraudRuleEngine {
        +evaluate(claim, facts) list
    }
    class TriageScorer {
        +score(facts, coverage, flags) TriageResult
    }
    class ClaimPipeline {
        +run(claim_id)
    }

    ClaimPipeline --> OcrProvider
    ClaimPipeline --> PiiMasker
    ClaimPipeline --> ClaimExtractor
    ClaimPipeline --> PolicyRetriever
    ClaimPipeline --> CoverageAssessor
    ClaimPipeline --> FraudRuleEngine
    ClaimPipeline --> TriageScorer
    PolicyRetriever --> EmbeddingProvider
```
