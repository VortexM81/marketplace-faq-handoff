from typing import Any, Mapping

from marketplace_faq import MarketplaceFaqIndex


class DecisionIndex(MarketplaceFaqIndex):
    def __init__(self) -> None:
        super().__init__(
            "test-faqs",
            api_key="test-key",
            transport=object(),
            embedder=lambda texts: [[0.2, 0.8] for _ in texts],
        )
        self.payloads: list[Mapping[str, Any]] = []

    def _post(self, path: str, payload: Mapping[str, Any], *, idempotency_key: str | None = None) -> Mapping[str, Any]:
        self.payloads.append(payload)
        if path.endswith("/query"):
            return {
                "matches": [
                    {
                        "id": "shipping-address",
                        "metadata": {
                            "question": "Can I change my shipping address?",
                            "answer": "Yes, before dispatch.",
                            "handoff_stage": "pre_dispatch",
                        },
                    },
                    {
                        "id": "gift-note",
                        "metadata": {
                            "question": "Can the seller add a gift note?",
                            "answer": "Message the seller before dispatch.",
                            "handoff_stage": "pre_dispatch",
                        },
                    },
                ]
            }
        return {"results": [{"candidate": "Can I change my shipping address?"}]}


def test_buyer_update_is_filtered_by_handoff_stage_and_reranked() -> None:
    index = DecisionIndex()

    suggestions = index.suggest("Send it to my office instead", "pre_dispatch", limit=1)

    assert [item.faq_id for item in suggestions] == ["shipping-address"]
    assert suggestions[0].answer == "Yes, before dispatch."
    assert index.payloads[0]["filter"] == {"handoff_stage": "pre_dispatch"}
    assert index.payloads[1]["top_k"] == 1
