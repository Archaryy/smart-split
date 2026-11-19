
import re
from decimal import Decimal, InvalidOperation


# Matches Indonesian-style monetary amounts.
AMOUNT_PATTERN = re.compile(
    r"(?<!\w)(?:Rp\.?\s*|IDR\s*)"
    r"(\d{1,3}(?:[.,]\d{3})+|\d+)",
    re.IGNORECASE
)

# A numbered line starts a new receipt item.
ITEM_PATTERN = re.compile(r"^\s*\d+[.)]\s*(.+)$")

# Examples:
# 1 lusin x 36,000
# 1 500 ml x 7,000
# 1 x 27,000
DETAIL_PATTERN = re.compile(
    r"^\s*(\d+)\s*(.*?)\s*[x×]\s*"
    r"((?:\d{1,3}(?:[.,]\d{3})+)|\d+)\s*$",
    re.IGNORECASE
)

SUMMARY_LABELS = {
    "subtotal": ["subtotal", "sub total"],
    "tax": ["tax", "ppn", "vat", "pajak"],
    "service_charge": [
        "service charge",
        "biaya layanan",
        "biaya service"
    ],
    "discount": ["discount", "diskon", "potongan"],
    "total": [
        "grand total",
        "total bayar",
        "amount due",
        "total pembayaran",
        "total"
    ]
}


def parse_amount(value: str) -> Decimal:
    """Convert Indonesian monetary notation into Decimal."""

    value = re.sub(r"(?i)Rp\.?|IDR", "", value)
    value = value.replace(" ", "")

    if "," in value and "." in value:
        # The last separator determines the decimal/thousands convention.
        last_separator = max(value.rfind(","), value.rfind("."))

        if len(value) - last_separator - 1 == 3:
            value = value.replace(",", "").replace(".", "")
        else:
            value = (
                value[:last_separator]
                .replace(",", "")
                .replace(".", "")
                + "."
                + value[last_separator + 1:]
            )

    elif "," in value or "." in value:
        separator = "," if "," in value else "."
        parts = value.split(separator)

        if len(parts[-1]) == 3:
            value = "".join(parts)
        else:
            value = ".".join(parts)

    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"Invalid monetary value: {value}")


def find_rupiah_amount(text: str):
    """Return an explicit Rp/IDR amount, if present."""

    match = AMOUNT_PATTERN.search(text)

    if not match:
        return None

    return parse_amount(match.group(1))


def identify_summary_field(text: str):
    """Identify subtotal, tax, service charge, discount or total."""

    normalized = text.lower().strip()
    normalized = re.sub(r"[:\s]+$", "", normalized)

    for field in [
        "subtotal",
        "service_charge",
        "discount",
        "tax",
        "total"
    ]:
        for label in SUMMARY_LABELS[field]:
            if re.search(
                r"\b" + re.escape(label) + r"\b",
                normalized
            ):
                if field == "total" and "subtotal" in normalized:
                    continue

                return field

    return None


def parse_item_details(text: str):
    """Extract quantity, unit and line total from an item detail."""

    match = DETAIL_PATTERN.match(text)

    if not match:
        return None

    quantity = int(match.group(1))
    unit = match.group(2).strip().lower()
    line_total = parse_amount(match.group(3))

    if unit == "lusin":
        quantity *= 12
        unit = "pcs"
    elif not unit:
        unit = "pcs"

    unit_price = line_total / Decimal(quantity)

    return {
        "quantity": quantity,
        "unit": unit,
        "unit_price": unit_price,
        "total_price": line_total
    }


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

    current_item = None
    pending_summary = None
    in_payment_history = False

    def finish_item():
        nonlocal current_item

        if current_item is None:
            return

        if current_item["total_price"] is None:
            current_item["total_price"] = Decimal("0")

        if current_item["unit_price"] is None:
            quantity = current_item["quantity"]
            if quantity > 0:
                current_item["unit_price"] = (
                    current_item["total_price"] / Decimal(quantity)
                )
            else:
                current_item["unit_price"] = Decimal("0")

        receipt["items"].append(current_item)
        current_item = None

    for index, line in enumerate(lines):
        text = line.get("text", "").strip()

        if not text:
            continue

        normalized = text.lower()

        # Ignore payment history and everything after it.
        if "history pembayaran" in normalized:
            finish_item()
            in_payment_history = True
            continue

        if in_payment_history:
            continue

        # First OCR line is usually the merchant name.
        if receipt["merchant_name"] is None and index == 0:
            receipt["merchant_name"] = text
            continue

        # Identify a summary label. Its amount may be on the next line.
        summary_field = identify_summary_field(text)

        if summary_field:
            finish_item()

            amount = find_rupiah_amount(text)

            if amount is not None:
                receipt[summary_field] = amount
                pending_summary = None
            else:
                pending_summary = summary_field

            continue

        # Resolve a summary amount appearing on its own line.
        if pending_summary:
            amount = find_rupiah_amount(text)

            if amount is not None:
                receipt[pending_summary] = amount
                pending_summary = None
                continue

            pending_summary = None

        # Ignore non-item metadata.
        if any(keyword in normalized for keyword in [
            "no. telp",
            "sisa limit",
            "status:",
            "tipe:",
            "due:",
            "total qty",
            "terimakasih"
        ]):
            continue

        # A numbered product name starts a new item.
        item_match = ITEM_PATTERN.match(text)

        if item_match:
            finish_item()

            current_item = {
                "name": item_match.group(1).strip(),
                "quantity": 1,
                "unit": "pcs",
                "unit_price": None,
                "total_price": None,
                "confidence": line.get("confidence")
            }
            continue

        if current_item is None:
            continue

        # Read item details such as quantity, unit and price.
        details = parse_item_details(text)

        if details:
            current_item.update(details)
            continue

        # Explicit Rp amount belongs to the current item.
        amount = find_rupiah_amount(text)

        if amount is not None:
            current_item["total_price"] = amount

            quantity = current_item["quantity"]

            if quantity > 0:
                current_item["unit_price"] = (
                    amount / Decimal(quantity)
                )

    finish_item()

    return receipt
