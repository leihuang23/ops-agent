from __future__ import annotations

import functools
import hashlib
import logging
import math
import random
import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol

import httpx

from app.models import KNOWLEDGE_EMBEDDING_DIMENSIONS

if TYPE_CHECKING:
    from app.core.config import Settings

TOKEN_RE = re.compile(r"[a-z0-9]+")
logger = logging.getLogger(__name__)

OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
OPENAI_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
ZHIPU_EMBEDDING_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
# Zhipu's embedding-3 model only supports 256/512/1024/2048 output
# dimensions; request the smallest and project down locally.
ZHIPU_REQUEST_DIMENSIONS = 256
# Zhipu accepts at most 64 input texts per embeddings request.
ZHIPU_MAX_BATCH_SIZE = 64


def tokenize(text: str) -> list[str]:
    return [normalize_token(token) for token in TOKEN_RE.findall(text.lower())]


def normalize_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def embed_text(text: str, dimensions: int = KNOWLEDGE_EMBEDDING_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    tokens = tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    numerator = sum(a * b for a, b in zip(left_values, right_values, strict=False))
    left_magnitude = math.sqrt(sum(value * value for value in left_values))
    right_magnitude = math.sqrt(sum(value * value for value in right_values))
    if left_magnitude == 0 or right_magnitude == 0:
        return 0.0
    return numerator / (left_magnitude * right_magnitude)


class EmbeddingProvider(Protocol):
    """Protocol for text embedding implementations."""

    @property
    def dimensions(self) -> int:
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class LocalHashingEmbeddings:
    """Deterministic hashing-based embeddings used by default.

    Requires no external API keys and is fully reproducible across runs.
    """

    @property
    def dimensions(self) -> int:
        return KNOWLEDGE_EMBEDDING_DIMENSIONS

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [embed_text(text) for text in texts]


class OpenAIEmbeddings:
    """OpenAI API-backed embeddings projected to the configured dimension."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        output_dimensions: int = KNOWLEDGE_EMBEDDING_DIMENSIONS,
        timeout_seconds: int = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.provider = "openai"
        self.model = model
        self._api_key = api_key
        self._output_dimensions = output_dimensions
        self._timeout = timeout_seconds
        self._transport = transport
        self._input_dimensions = OPENAI_EMBEDDING_DIMENSIONS.get(model, 1536)

    @property
    def dimensions(self) -> int:
        return self._output_dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload: dict[str, object] = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        # OpenAI supports native dimension reduction for v3 models; request the
        # smallest valid dimension and project the rest locally.
        if self.model.startswith("text-embedding-3"):
            min_dimension = 512 if self.model == "text-embedding-3-small" else 256
            payload["dimensions"] = max(min_dimension, self._output_dimensions)

        with httpx.Client(transport=self._transport) as client:
            response = client.post(
                OPENAI_EMBEDDING_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            raw = response.json()

        ordered: list[list[float]] = [[] for _ in texts]
        for item in raw["data"]:
            ordered[item["index"]] = item["embedding"]

        return [_project_to_dimensions(vector, self._output_dimensions) for vector in ordered]


class ZhipuEmbeddings:
    """Zhipu (BigModel) API-backed embeddings projected to the configured dimension."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "embedding-3",
        output_dimensions: int = KNOWLEDGE_EMBEDDING_DIMENSIONS,
        timeout_seconds: int = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.provider = "zhipu"
        self.model = model
        self._api_key = api_key
        self._output_dimensions = output_dimensions
        self._timeout = timeout_seconds
        self._transport = transport

    @property
    def dimensions(self) -> int:
        return self._output_dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        ordered: list[list[float]] = [[] for _ in texts]
        with httpx.Client(transport=self._transport) as client:
            for batch_start in range(0, len(texts), ZHIPU_MAX_BATCH_SIZE):
                batch = texts[batch_start : batch_start + ZHIPU_MAX_BATCH_SIZE]
                response = client.post(
                    ZHIPU_EMBEDDING_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": batch,
                        "dimensions": ZHIPU_REQUEST_DIMENSIONS,
                    },
                    timeout=self._timeout,
                )
                response.raise_for_status()
                raw = response.json()

                for item in raw["data"]:
                    ordered[batch_start + item["index"]] = item["embedding"]

        return [_project_to_dimensions(vector, self._output_dimensions) for vector in ordered]


def _project_to_dimensions(vector: list[float], dimensions: int) -> list[float]:
    """Project a high-dimensional vector down to a fixed output dimension.

    Uses a deterministic random projection matrix shared by all vectors with
    the same input/output dimensions, so pairwise cosine structure survives
    the projection (Johnson-Lindenstrauss style) instead of degenerating to
    noise. The projected vector is L2-normalized to remain compatible with
    cosine-similarity search.
    """
    if len(vector) == dimensions:
        return _normalize(vector)

    matrix = _projection_matrix(len(vector), dimensions)
    projected: list[float] = [0.0] * dimensions
    for input_index, value in enumerate(vector):
        row = matrix[input_index]
        for dim_index in range(dimensions):
            projected[dim_index] += value * row[dim_index]

    return _normalize(projected)


@functools.lru_cache(maxsize=8)
def _projection_matrix(input_dim: int, output_dim: int) -> tuple[tuple[float, ...], ...]:
    """Deterministic Gaussian projection matrix for a dimension pair.

    Seeded only by the dimension pair (never by the vector contents) so every
    vector is projected through the same matrix. Cached because ingestion
    projects many vectors of identical shape.
    """
    rng = random.Random(f"ledger-embedding-projection-v1:{input_dim}:{output_dim}")
    scale = 1.0 / math.sqrt(output_dim)
    return tuple(
        tuple(rng.gauss(0.0, scale) for _ in range(output_dim))
        for _ in range(input_dim)
    )


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def get_embedding_provider(
    settings: Settings | None = None,
) -> EmbeddingProvider:
    """Return the configured embedding provider.

    Falls back to the local hashing provider when OpenAI or Zhipu is requested
    but no API key is configured, so default behavior is unchanged without
    credentials.
    """
    from app.core.config import get_settings

    resolved: Settings = settings or get_settings()
    if resolved.embedding_provider == "openai" and resolved.openai_api_key:
        return OpenAIEmbeddings(
            api_key=resolved.openai_api_key,
            model=resolved.openai_embedding_model,
        )

    if resolved.embedding_provider == "openai" and not resolved.openai_api_key:
        logger.warning(
            "EMBEDDING_PROVIDER=openai requested but OPENAI_API_KEY is empty; "
            "falling back to local hashing embeddings."
        )

    if resolved.embedding_provider == "zhipu" and resolved.zhipu_api_key:
        return ZhipuEmbeddings(
            api_key=resolved.zhipu_api_key,
            model=resolved.zhipu_embedding_model,
        )

    if resolved.embedding_provider == "zhipu" and not resolved.zhipu_api_key:
        logger.warning(
            "EMBEDDING_PROVIDER=zhipu requested but ZHIPU_API_KEY is empty; "
            "falling back to local hashing embeddings."
        )

    return LocalHashingEmbeddings()
