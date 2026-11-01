"""SQS consumer that runs the claim pipeline (docs/diagrams/sequence-claim-processing.md)."""

import logging

from app.core.config import settings

log = logging.getLogger("claimlens.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("Claim worker starting; queue=%s", settings.claims_queue_url)
    # Roadmap: long-poll SQS, run ClaimPipeline.run(claim_id) per message,
    # delete on success, let the visibility timeout expire on failure (DLQ after 3).
    raise NotImplementedError("Roadmap: document upload and SQS pipeline")


if __name__ == "__main__":
    main()
