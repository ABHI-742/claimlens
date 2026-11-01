"""S3 and SQS adapters against LocalStack. Skipped unless LOCALSTACK_URL is set."""

import os
import uuid

import boto3
import pytest

LOCALSTACK = os.environ.get("LOCALSTACK_URL")
pytestmark = pytest.mark.skipif(not LOCALSTACK, reason="LOCALSTACK_URL not set")


@pytest.fixture
def aws(monkeypatch):
    from app.core.config import settings

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setattr(settings, "aws_endpoint_url", LOCALSTACK)
    monkeypatch.setattr(settings, "aws_public_endpoint_url", LOCALSTACK)
    return settings


def test_s3_storage_round_trip_and_presign(aws):
    from app.services.storage import S3Storage

    bucket = f"test-{uuid.uuid4().hex[:8]}"
    boto3.client("s3", region_name="us-east-1", endpoint_url=LOCALSTACK).create_bucket(Bucket=bucket)
    storage = S3Storage(bucket=bucket)
    storage.put_bytes("a/b.txt", b"hello", "text/plain")

    assert storage.get_bytes("a/b.txt") == b"hello"
    assert storage.presign_put("a/c.txt", "text/plain").startswith(LOCALSTACK)


def test_sqs_queue_send_receive_delete(aws):
    from app.services.job_queue import SqsQueue

    url = boto3.client("sqs", region_name="us-east-1", endpoint_url=LOCALSTACK).create_queue(
        QueueName=f"test-{uuid.uuid4().hex[:8]}"
    )["QueueUrl"]
    queue = SqsQueue(queue_url=url)
    queue.send("claim.submitted", "abc")

    [job] = queue.receive(wait_seconds=1)
    assert (job.type, job.id, job.attempt) == ("claim.submitted", "abc", 1)
    queue.delete(job)
    assert queue.receive(wait_seconds=1) == []
