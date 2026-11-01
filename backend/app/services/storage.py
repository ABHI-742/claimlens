"""S3 document storage. LocalStack locally, real S3 in AWS."""

from typing import Protocol

import boto3

from app.core.config import settings


class Storage(Protocol):
    def presign_put(self, key: str, mime_type: str) -> str: ...
    def presign_get(self, key: str) -> str: ...
    def get_bytes(self, key: str) -> bytes: ...
    def put_bytes(self, key: str, data: bytes, mime_type: str) -> None: ...


class S3Storage:
    def __init__(self, bucket: str = settings.documents_bucket) -> None:
        self.bucket = bucket
        self._s3 = boto3.client("s3", region_name=settings.aws_region, endpoint_url=settings.aws_endpoint_url)
        # Presigned URLs are opened by the browser, so they must use a host it can reach.
        self._public = boto3.client(
            "s3",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_public_endpoint_url or settings.aws_endpoint_url,
        )

    def presign_put(self, key: str, mime_type: str) -> str:
        return self._public.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": mime_type},
            ExpiresIn=settings.presign_ttl_seconds,
        )

    def presign_get(self, key: str) -> str:
        return self._public.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=settings.presign_ttl_seconds
        )

    def get_bytes(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def put_bytes(self, key: str, data: bytes, mime_type: str) -> None:
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime_type)
