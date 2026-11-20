"""Read a receipt image: OCR + parsing, retrying with other image variants if needed."""

from __future__ import annotations

import logging
from typing import Callable

from app.services.receipt_parser import parse_receipt_text

logger = logging.getLogger("smartsplit.pipeline")

# Tried in order until one gives a trustworthy result, cheapest first:
#   * the small model on the plain image - a few seconds, right for most receipts;
#   * the small model on a contrast-boosted image - helps faint/tinted/shadowed photos
#     (the boost can amplify noise, so it is not the default);
#   * the slow medium model, as a last resort for hard photos.
ATTEMPTS = (
    ("small", "original"),
    ("small", "enhanced"),
    ("medium", "original"),
    ("medium", "enhanced"),
)


def _mean_confidence(ocr: dict) -> float:
    values = [line["confidence"] for line in ocr.get("lines", []) if line.get("confidence") is not None]
    return sum(values) / len(values) if values else 0.0


def score_result(ocr: dict, receipt: dict) -> float:
    """Higher is better. Reading items and matching the printed total matter most."""
    reconciliation = receipt["reconciliation"]
    status = reconciliation["status"]
    if not receipt["items"]:
        return _mean_confidence(ocr) * 0.5

    bonus = {"ok": 3.0, "unverified": 1.5, "mismatch": 1.0}.get(status, 0.0)

    # Among imperfect reads, prefer the one whose items land closest to the printed amount.
    closeness = 0.0
    if status == "mismatch":
        if reconciliation.get("printed_subtotal"):
            target, found = reconciliation["printed_subtotal"], reconciliation.get("items_sum")
        else:
            target, found = reconciliation.get("printed_total"), reconciliation.get("computed_total")
        if target and found is not None:
            closeness = max(0.0, 1 - abs(found - target) / target)

    return 1.0 + bonus + closeness + _mean_confidence(ocr) + 0.01 * min(len(receipt["items"]), 50)


def is_trustworthy(ocr: dict, receipt: dict) -> bool:
    status = receipt["reconciliation"]["status"]
    if not receipt["items"]:
        return False
    return status == "ok" or (status == "unverified" and _mean_confidence(ocr) >= 0.9)


def read_receipt(
    image_path,
    extract: Callable[..., dict],
    parse: Callable[[dict], dict] = parse_receipt_text,
    attempts=ATTEMPTS,
):
    """Return (ocr, receipt) for the best attempt.

    `extract(path, variant, model)` runs OCR. The first attempt that yields a
    trustworthy parse wins immediately, so ordinary receipts pay for a single
    fast OCR pass.
    """
    best = None

    for model, variant in attempts:
        ocr = extract(image_path, variant, model)
        receipt = parse(ocr)
        score = score_result(ocr, receipt)
        logger.info("model=%s variant=%s items=%d status=%s score=%.2f",
                    model, variant, len(receipt["items"]), receipt["reconciliation"]["status"], score)

        if best is None or score > best[0]:
            best = (score, ocr, receipt)

        if is_trustworthy(ocr, receipt):
            break

    _, ocr, receipt = best
    return ocr, receipt
