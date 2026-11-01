# ADR-0003: Mask PII before any LLM call

**Status:** Accepted

## Context
Claim documents contain SSNs, bank details, card numbers and contact information. Sending them to an external model increases compliance risk and is not needed for extraction or coverage reasoning.

## Decision
After OCR, a `PiiMasker` replaces detected values with stable tokens such as `[SSN_1]` and `[CARD_1]`. The token map stays in worker memory for the run and is then discarded: it is never stored and never included in prompts, so there is no mapping back to raw values to protect. Stored OCR text is the masked version.

## Consequences
- The model can still reason about structure, for example that the same card token appears on two invoices
- Detectors need tests for both recall and false positives
- Unmasking happens only when displaying data to authorized users
