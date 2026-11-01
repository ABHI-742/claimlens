"""Embedding providers. All return unit-length vectors of settings.embedding_dimensions."""

import hashlib
import json
import math
import re

import boto3

from app.core.config import settings
from app.services.interfaces import EmbeddingProvider

_TOKEN = re.compile(r"[a-z0-9]+")


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class HashEmbeddings:
    """Dependency-free bag-of-words embedding (feature hashing of words and word pairs).

    Good enough for local development and tests; use Bedrock or a local model for real retrieval quality.
    """

    def __init__(self, dimensions: int = settings.embedding_dimensions) -> None:
        self.dimensions = dimensions

    def _bucket(self, feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        return value % self.dimensions, 1.0 if value & 1 else -1.0

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            tokens = _TOKEN.findall(text.lower())
            vector = [0.0] * self.dimensions
            for feature in tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]:
                index, sign = self._bucket(feature)
                vector[index] += sign
            vectors.append(_normalize(vector))
        return vectors


class BedrockTitanEmbeddings:
    def __init__(self) -> None:
        self._client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            body = json.dumps(
                {"inputText": text, "dimensions": settings.embedding_dimensions, "normalize": True}
            )
            response = self._client.invoke_model(modelId=settings.bedrock_embedding_model, body=body)
            vectors.append(json.loads(response["body"].read())["embedding"])
        return vectors


class LocalModelEmbeddings:
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(settings.local_embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def build_embeddings() -> EmbeddingProvider:
    if settings.embedding_provider == "bedrock":
        return BedrockTitanEmbeddings()
    if settings.embedding_provider == "local":
        return LocalModelEmbeddings()
    return HashEmbeddings()
