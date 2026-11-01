"""SQS job queue (ADR-0002). Messages are JSON: {"type": "...", "id": "..."}."""

import json
from dataclasses import dataclass
from typing import Protocol

import boto3

from app.core.config import settings

CLAIM_SUBMITTED = "claim.submitted"
POLICY_UPLOADED = "policy.uploaded"


@dataclass(frozen=True)
class Job:
    type: str
    id: str
    receipt_handle: str = ""
    attempt: int = 1


class JobQueue(Protocol):
    def send(self, job_type: str, entity_id: str) -> None: ...
    def receive(self, max_messages: int = 5, wait_seconds: int = 20) -> list[Job]: ...
    def delete(self, job: Job) -> None: ...


class SqsQueue:
    def __init__(self, queue_url: str = settings.claims_queue_url) -> None:
        self.queue_url = queue_url
        self._sqs = boto3.client(
            "sqs", region_name=settings.aws_region, endpoint_url=settings.aws_endpoint_url
        )

    def send(self, job_type: str, entity_id: str) -> None:
        self._sqs.send_message(
            QueueUrl=self.queue_url, MessageBody=json.dumps({"type": job_type, "id": entity_id})
        )

    def receive(self, max_messages: int = 5, wait_seconds: int = 20) -> list[Job]:
        response = self._sqs.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_seconds,
            MessageSystemAttributeNames=["ApproximateReceiveCount"],
        )
        jobs = []
        for message in response.get("Messages", []):
            body = json.loads(message["Body"])
            attempt = int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
            jobs.append(
                Job(
                    type=body["type"], id=body["id"], receipt_handle=message["ReceiptHandle"], attempt=attempt
                )
            )
        return jobs

    def delete(self, job: Job) -> None:
        self._sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=job.receipt_handle)
