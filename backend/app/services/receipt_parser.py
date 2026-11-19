
import re
from decimal import Decimal, InvalidOperation


# Matches currency amounts such as:
# Rp25.000, 25,000, 25000, IDR 25.000
AMOUNT_PATTERN = re.compile(
    r"(?<!\w)(?:(?:Rp\.?|IDR)\s*)?"
    r"(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d{4,}(?:[.,]\d{1,2})?)"
    r"(?!\w)",
    re.IGNORECASE
)

SUMMARY_LABELS = {
    "subtotal": [
        "subtotal", "sub total"
    ],
    "tax": [
        "tax", "ppn", "vat", "pajak"
    ],
    "service_charge": [
        "service charge", "service", "biaya layanan"
    ],
    "discount": [
        "discount", "diskon", "potongan"
    ],
    "total": [
        "grand total", "total bayar", "amount due",
        "total pembayaran", "total"
    ]
}


def parse_amount(value: str) -> Decimal:
    """Convert Indonesian or English currency notation into Decimal."""

    value = re.sub(r"(?i)Rp\.?|IDR", "", value)
    value = value.replace(" ", "")

    if "," in value and "." in value:
        # Last separator determines decimal notation
        last_separator = max(value.rfind(","), value.rfind("."))

        if len(value) - last_separator - 1 == 3:
            value = value.replace(",", "").replace(".", "")
        else:
            value = value[:last_separator].replace(",", "").replace(".", "") \
                + "." + value[last_separator + 1:]

    elif "," in value or "." in value:
        separator = "," if "," in value else "."
        parts = value.split(separator)

        if len(parts[-1]) == 3:
            value = "".join(parts)
        else:
            value = separator.join(parts[:-1]) + "." + parts[-1]

    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"Invalid monetary value: {value}")


def get_line_amounts(text: str) -> list[Decimal]:
    matches = AMOUNT_PATTERN.findall(text)

    amounts = []

    for match in matches:
        try:
            amounts.append(parse_amount(match))
        except ValueError:
            continue

    return amounts


def identify_summary_field(text: str):
    normalized = text.lower().strip()

    # Check specific labels before generic "total"
    for field in ["subtotal", "service_charge", "discount", "tax", "total"]:
        for label in SUMMARY_LABELS[field]:
            if re.search(r"\b" + re.escape(label) + r"\b", normalized):
                if field == "total" and "subtotal" in normalized:
                    continue
                return field

    return None


def parse_receipt_text(ocr_result: dict) -> dict:
    lines = ocr_result.get("lines", [])

    receipt = {
        "merchant_name": None,
        "currency": "IDR",
        "items": [],
        "subtotal": Decimal("0"),
        "tax": Decimal("0"),
        "service_charge": Decimal("0"),
        "discount": Decimal("0"),
        "total": Decimal("0")
    }

    for index, line in enumerate(lines):
        text = line["text"].strip()

        if not text:
            continue

        amounts = get_line_amounts(text)
        field = identify_summary_field(text)

        if field and amounts:
            receipt[field] = amounts[-1]
            continue

        # Preserve possible item lines for later refinement
        if amounts:
            receipt["items"].append({
                "description": text,
                "amounts": amounts,
                "confidence": line.get("confidence")
            })

        # Use the first non-empty line as a merchant candidate
        elif receipt["merchant_name"] is None and index == 0:
            receipt["merchant_name"] = text

    return receipt