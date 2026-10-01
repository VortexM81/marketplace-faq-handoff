"""Runnable example that models seller assets and a buyer order update."""

from marketplace_faq import MarketplaceFaqIndex, SellerFaq


def main() -> None:
    index = MarketplaceFaqIndex(collection="seller-order-faqs")
    index.prepare(
        [
            SellerFaq("shipping-address", "Can I change my shipping address?", "Yes, before dispatch.", "pre_dispatch"),
            SellerFaq("tracking", "Where can I find tracking?", "Tracking appears after dispatch.", "post_dispatch"),
            SellerFaq("gift-note", "Can the seller add a gift note?", "Message the seller before dispatch.", "pre_dispatch"),
        ]
    )
    suggestions = index.suggest("I need this sent to my office instead", "pre_dispatch", limit=2)
    for item in suggestions:
        print(f"{item.question} -> {item.answer}")


if __name__ == "__main__":
    main()

