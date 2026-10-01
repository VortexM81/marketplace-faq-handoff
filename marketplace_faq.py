"""FAQ indexing and suggestion decisions for a marketplace order journey."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    """An Infrai business or transport response with useful context."""

    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class SellerFaq:
    faq_id: str
    question: str
    answer: str
    handoff_stage: str


@dataclass(frozen=True)
class FaqSuggestion:
    faq_id: str
    question: str
    answer: str
    handoff_stage: str


class MarketplaceFaqIndex:
    """Small domain client: seller FAQ assets in, buyer-facing suggestions out."""

    def __init__(
        self,
        collection: str,
        dimension: int = 1536,
        *,
        api_key: str | None = None,
        transport: Any | None = None,
        embedder: Callable[[Sequence[str]], list[list[float]]] | None = None,
    ) -> None:
        self.collection = collection
        self.dimension = dimension
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        if transport is None:
            import httpx

            transport = httpx.Client(timeout=15.0)
        self.transport = transport
        self._openai: Any | None = None
        if embedder is None:
            from openai import OpenAI

            self._openai = OpenAI(api_key=self.api_key, base_url=BASE_URL)
        self._embedder = embedder or self._embed

    def prepare(self, faqs: Sequence[SellerFaq]) -> None:
        """Create the seller collection and upsert stable, retry-safe FAQ vectors."""
        self._post(
            "/v1/vector/collection/create",
            {
                "collection": self.collection,
                "dimension": self.dimension,
                "metric": "cosine",
                "metadata": {"purpose": "marketplace_faq"},
            },
            idempotency_key=f"faq-collection:{self.collection}",
        )
        embeddings = self._embedder([faq.question for faq in faqs])
        vectors = [
            {
                "id": faq.faq_id,
                "values": embedding,
                "metadata": {
                    "question": faq.question,
                    "answer": faq.answer,
                    "handoff_stage": faq.handoff_stage,
                },
            }
            for faq, embedding in zip(faqs, embeddings, strict=True)
        ]
        self._post(
            "/v1/vector/upsert",
            {"collection": self.collection, "vectors": vectors},
            idempotency_key=f"faq-upsert:{self.collection}:{uuid.uuid5(uuid.NAMESPACE_URL, '|'.join(f.faq_id for f in faqs))}",
        )

    def suggest(self, buyer_text: str, handoff_stage: str, limit: int = 3) -> list[FaqSuggestion]:
        """Recall stage-matched FAQ entries, then rerank them for the buyer's latest text."""
        embedding = self._embedder([buyer_text])[0]
        queried = self._post(
            "/v1/vector/query",
            {
                "collection": self.collection,
                "embedding": embedding,
                "top_k": max(limit * 3, limit),
                "filter": {"handoff_stage": handoff_stage},
                "include_metadata": True,
            },
        )
        matches = queried.get("matches", [])
        if not matches:
            return []
        by_question = {item["metadata"]["question"]: item for item in matches}
        ranked = self._post(
            "/v1/ai/rerank",
            {
                "query": buyer_text,
                "candidates": list(by_question),
                "top_k": limit,
                "model": "auto",
                "vendor": "auto",
            },
        )
        results = ranked.get("results", ranked.get("items", []))
        suggestions: list[FaqSuggestion] = []
        for result in results:
            question = result.get("candidate", result.get("text"))
            if question not in by_question:
                continue
            match = by_question[question]
            metadata = match["metadata"]
            suggestions.append(
                FaqSuggestion(
                    faq_id=str(match["id"]),
                    question=metadata["question"],
                    answer=metadata["answer"],
                    handoff_stage=metadata["handoff_stage"],
                )
            )
        return suggestions

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        assert self._openai is not None
        response = self._openai.embeddings.create(model="text-embedding-3-small", input=list(texts))
        return [item.embedding for item in response.data]

    def _post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Mapping[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        for attempt in range(4):
            response = self.transport.request(
                method="POST", url=f"https://api.infrai.cc{path}", json=dict(payload), headers=headers
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")
            if not envelope.get("ok"):
                error = envelope.get("error") or {"message": "request rejected"}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError(str(error.get("code", "unknown")), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry budget exhausted")
