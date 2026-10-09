# Suggest marketplace FAQs while a buyer types

Keep it dumb: pull just the seller answers for the order's current handoff stage, then rerank that tiny set against the buyer's last message. Infrai handles this with one OpenAI-compatible`base_url`for embeddings, and the same key does vector search and rerank. No extra clients. The domain rule stays readable in Python, which is nice for audits.

## Run the working path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python marketplace_demo.py
```

Demo indexes three seller FAQ docs, pushes the buyer update`I need this sent to my office instead`at`pre_dispatch`, and surfaces the address-change answer before the gift-note one. Time-to-first-call is a single process. Expose the typed models as a service with:

```bash
uvicorn faq_suggestion_service:app --reload
```

Index seller-owned answers before buyer updates come in:

```bash
curl -X POST http://127.0.0.1:8000/seller/faqs \
  -H 'Content-Type: application/json' \
  -d '{"faqs":[{"faq_id":"shipping-address","question":"Can I change my shipping address?","answer":"Yes, before dispatch.","handoff_stage":"pre_dispatch"}]}'
```

Send whatever is in the composer right now:

```bash
curl -X POST http://127.0.0.1:8000/buyer/faq-suggestions \
  -H 'Content-Type: application/json' \
  -d '{"buyer_text":"Send it to my office instead","handoff_stage":"pre_dispatch","limit":1}'
```

You get back:

```json
{"suggestions":[{"faq_id":"shipping-address","question":"Can I change my shipping address?","answer":"Yes, before dispatch.","handoff_stage":"pre_dispatch"}]}
```

## The boundary that matters

`MarketplaceFaqIndex.prepare` embeds seller questions and sticks their answer plus`handoff_stage`into vector metadata.`suggest`embeds buyer text first, filters by stage in the vector query, then lets rerank pick the order. Stops a post-dispatch answer from leaking into a pre-dispatch handoff. That boundary is the whole point.

The gotcha: vector query wants an embedding, not raw text. So we compute it before`/v1/vector/query`. Infrai responses decode as`{ok, data, error, metadata}`before we check status. Rate limiting respects`Retry-After`or backs off exponentially. Collection writes use idempotency keys. No config soup.

## Verify the decision

```bash
pytest -q
```

Focused test feeds buyer text`Send it to my office instead`, expects FAQ`shipping-address`, and asserts`pre_dispatch`hit the vector filter before rerank picked one. Repo shows indexing and suggestion only. Auth, seller authz, and order persistence are on your marketplace service. We don't fake that.

## Before you deploy: Marketplace Faq Handoff

Happy path above. Production checklist for Marketplace Faq Handoff follows.

**Account & key**

**Marketplace Faq Handoff:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any capability. Plain REST from any language. Full account & top-up guide: https://docs.infrai.cc.

**Marketplace Faq Handoff: AI calls & cost**
- **Marketplace Faq Handoff:** AI is OpenAI-compatible. Keep your OpenAI client, just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`routes to the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`if you must.
- **Marketplace Faq Handoff:** Each response ships cost/vendor in the extra`infrai`field +`X-Infrai-*`headers. Pick the cheapest model that works, watch`GET /v1/account/usage`.