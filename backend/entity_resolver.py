"""Transparent token coverage + edit similarity; no customer-specific mappings."""

import re
from difflib import SequenceMatcher

ALIASES = {
    "ind": "industrial",
    "supp": "supply",
    "mfg": "manufacturing",
    "med": "medical",
    "sys": "systems",
    "log": "logistics",
    "bldg": "building",
    "mat": "materials",
    "intl": "international",
}
STOP = {"llc", "inc", "ltd", "the", "and", "corp", "corporation", "co"}


def tokens(text):
    return [
        ALIASES.get(x, x) for x in re.findall(r"[a-z]+", text.lower()) if x not in STOP
    ]


def token_similarity(left, right):
    """Accept generic bank-feed truncation without customer-specific aliases."""
    if left == right:
        return 1.0
    short, long = sorted((left, right), key=len)
    if len(short) >= 3 and long.startswith(short):
        return 0.9
    return SequenceMatcher(None, left, right).ratio()


def name_score(memo, name):
    payer, canonical = tokens(memo), tokens(name)
    if not canonical:
        return 0.0
    similarities = [
        max((token_similarity(token, other) for other in payer), default=0)
        for token in canonical
    ]
    coverage = sum(1 if x >= 0.82 else 0 for x in similarities) / len(canonical)
    # Exact / abbreviated token matches dominate noisy bank-feed prose.
    return round(0.85 * coverage + 0.15 * sum(similarities) / len(canonical), 4)


def resolve_counterparty(memo, invoices, threshold=0.65):
    customers = {x.customer_id: x.customer_name for x in invoices}
    scores = sorted(
        [
            {"customer_id": key, "customer_name": name, "score": name_score(memo, name)}
            for key, name in customers.items()
        ],
        key=lambda x: (-x["score"], x["customer_id"]),
    )
    best = scores[0] if scores else None
    if not best or best["score"] < threshold:
        return {
            "customer_id": None,
            "customer_name": None,
            "score": best["score"] if best else 0,
            "reason": "No counterparty meets the confidence threshold",
            "candidates": scores[:3],
        }
    if len(scores) > 1 and best["score"] - scores[1]["score"] < 0.08:
        return {
            "customer_id": None,
            "customer_name": None,
            "score": best["score"],
            "reason": "Ambiguous counterparty; controller confirmation required",
            "candidates": scores[:3],
        }
    return {
        **best,
        "reason": "Deterministic token and edit-distance match",
        "candidates": scores[:3],
    }
