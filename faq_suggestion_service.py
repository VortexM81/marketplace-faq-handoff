"""Typed HTTP entry point for marketplace FAQ suggestions."""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from marketplace_faq import FaqSuggestion, InfraiError, MarketplaceFaqIndex, SellerFaq


class SellerFaqAsset(BaseModel):
    faq_id: str
    question: str
    answer: str
    handoff_stage: str


class IndexSellerAssetsRequest(BaseModel):
    faqs: list[SellerFaqAsset] = Field(min_length=1)


class BuyerUpdateRequest(BaseModel):
    buyer_text: str = Field(min_length=2)
    handoff_stage: str
    limit: int = Field(default=3, ge=1, le=10)


class SuggestionResponse(BaseModel):
    suggestions: list[FaqSuggestion]


app = FastAPI(title="Marketplace FAQ Suggestions")


def get_index() -> MarketplaceFaqIndex:
    return MarketplaceFaqIndex(collection=os.getenv("FAQ_COLLECTION", "seller-order-faqs"))


@app.post("/seller/faqs", status_code=204)
def index_seller_assets(request: IndexSellerAssetsRequest) -> None:
    try:
        get_index().prepare([SellerFaq(**faq.model_dump()) for faq in request.faqs])
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.post("/buyer/faq-suggestions", response_model=SuggestionResponse)
def suggest_for_buyer(request: BuyerUpdateRequest) -> SuggestionResponse:
    try:
        suggestions = get_index().suggest(request.buyer_text, request.handoff_stage, request.limit)
        return SuggestionResponse(suggestions=suggestions)
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

