# ADR-0001: pgvector instead of a dedicated vector database

**Status:** Accepted

## Context
ClaimLens needs similarity search over policy clauses: tens of thousands of chunks per insurer, not billions. Claims data already lives in PostgreSQL.

## Decision
Store embeddings in PostgreSQL with the `pgvector` extension and an HNSW index.

## Consequences
- One database to run, back up and secure; vectors join directly with policy metadata (product, version)
- A single transaction covers relational and vector writes
- HNSW gives low-latency approximate search at this scale
- If the corpus grows past tens of millions of vectors, revisit (OpenSearch or a managed vector store)
