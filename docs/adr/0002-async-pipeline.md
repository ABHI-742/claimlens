# ADR-0002: Asynchronous queue-based pipeline

**Status:** Accepted

## Context
OCR and LLM calls take seconds to minutes per claim and can fail transiently. Upload requests must stay fast.

## Decision
The API stores documents and enqueues a `claim.submitted` message on SQS. A separate worker processes the claim. Messages are retried up to 3 times using the visibility timeout, then moved to a dead-letter queue.

## Consequences
- Upload latency does not depend on processing time
- Workers scale horizontally on queue depth
- Each pipeline stage must be idempotent, keyed by claim ID and stage name
- The UI polls claim status (or receives server-sent events in a later version)
