import json
from typing import Any

import boto3  # type: ignore[import-untyped]
import structlog

from bulldogent.embedding.config import BedrockEmbeddingConfig
from bulldogent.embedding.provider import AbstractEmbeddingProvider

_logger = structlog.get_logger()

_MAX_BATCH_SIZE = 2048


class BedrockEmbeddingProvider(AbstractEmbeddingProvider):
    config: BedrockEmbeddingConfig

    def __init__(self, config: BedrockEmbeddingConfig) -> None:
        super().__init__(config)
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=config.region,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = texts[i : i + _MAX_BATCH_SIZE]
            _logger.debug("embedding_batch", batch_size=len(batch), offset=i)

            request_body: dict[str, Any] = {
                "inputText": batch[0] if len(batch) == 1 else None,
                "texts": batch if len(batch) > 1 else None,
            }
            # Bedrock Titan expects "inputText" for single, Cohere expects "texts"
            # Use the format appropriate for the model
            if len(batch) == 1:
                request_body = {"inputText": batch[0]}
            else:
                request_body = {"texts": batch, "input_type": "search_document"}

            response = self._client.invoke_model(
                modelId=self.config.model,
                body=json.dumps(request_body),
            )

            response_body = json.loads(response["body"].read())

            if "embedding" in response_body:
                # Titan single-text response
                all_embeddings.append(response_body["embedding"])
            elif "embeddings" in response_body:
                # Cohere / multi-text response
                all_embeddings.extend(response_body["embeddings"])

        return all_embeddings
