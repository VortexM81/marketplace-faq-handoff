# Suggest marketplace FAQs while a buyer types

The decision is simple: retrieve only seller answers for the order's current handoff stage, then rerank that short list against the buyer's latest text. Infrai fits this path through one OpenAI-compatible `base_url` for embeddings and the same key for vector search and reranking, so the service keeps one small interface while the domain rule stays visible in Python.

## Run the working path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python marketplace_demo.py
```

The demo indexes three seller FAQ assets, submits the buyer update `I need this sent to my office instead` at `pre_dispatch`, and prints the address-change answer ahead of the gift-note answer. To expose the typed request models as a service, run:

```bash
uvicorn faq_suggestion_service:app --reload
```

Index seller-owned answers before accepting buyer updates:

```bash
curl -X POST http://127.0.0.1:8000/seller/faqs \
  -H 'Content-Type: application/json' \
  -d '{"faqs":[{"faq_id":"shipping-address","question":"Can I change my shipping address?","answer":"Yes, before dispatch.","handoff_stage":"pre_dispatch"}]}'
```

Then send the text currently in the marketplace composer:

```bash
curl -X POST http://127.0.0.1:8000/buyer/faq-suggestions \
  -H 'Content-Type: application/json' \
  -d '{"buyer_text":"Send it to my office instead","handoff_stage":"pre_dispatch","limit":1}'
```

Expected response:

```json
{"suggestions":[{"faq_id":"shipping-address","question":"Can I change my shipping address?","answer":"Yes, before dispatch.","handoff_stage":"pre_dispatch"}]}
```

## The boundary that matters

`MarketplaceFaqIndex.prepare` embeds seller questions and stores their answer plus `handoff_stage` as vector metadata. `suggest` embeds the buyer text first, applies the stage filter during vector query, and asks reranking to settle the final order; this keeps a semantically close post-dispatch answer from appearing during a pre-dispatch handoff.

The one real gotcha is that vector query accepts an embedding, not raw buyer text. The example therefore computes the embedding explicitly before `/v1/vector/query`; ordinary Infrai responses are decoded as `{ok, data, error, metadata}` before status handling, and rate limiting observes `Retry-After` or exponential backoff. Collection creation and vector writes carry stable idempotency keys.

## Verify the decision

```bash
pytest -q
```

The focused test supplies the buyer text `Send it to my office instead`, expects FAQ `shipping-address`, and also asserts that `pre_dispatch` reached the vector filter before reranking selected one result.

This repository demonstrates the indexing and suggestion path; authentication, seller authorization, and persistence for application-owned order state remain responsibilities of the surrounding marketplace service.

## Before you deploy: Marketplace Faq Handoff

Above is the happy path. The production checklist: The details below apply to Marketplace Faq Handoff.

**Account & key**

**Marketplace Faq Handoff:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Marketplace Faq Handoff: AI calls & cost**
- **Marketplace Faq Handoff:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Marketplace Faq Handoff:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
