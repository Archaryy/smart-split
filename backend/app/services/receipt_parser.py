"""Turn OCR output into structured receipt data.

The parser is layout-driven rather than template-driven:

1. OCR fragments are grouped into visual rows using their bounding boxes
   (and de-skewed first when the photo is tilted).
2. Every row is tokenised and its monetary values are located.
3. Rows are classified (item / subtotal / tax / total / payment / metadata)
   from multilingual keywords (English + Indonesian).
4. Items are read from the rows above the first summary row, supporting
   one-line items, two-line items (name, then "2 x 15.000   30.000"),
   numbered items and column layouts ("NAME  qty  unit  total").
5. Printed totals are cross-checked against the item prices so the UI can
   tell the user whether the read looks trustworthy.

Line totals are treated as the source of truth; quantity and unit price are
derived from them.
"""

from __future__ import annotations

import difflib
import math
import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

_MONEY_BODY = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
MONEY_TOKEN = re.compile(rf"^(?P<body>{_MONEY_BODY})$")
_MONEY = rf"(?:{_MONEY_BODY})"
_QTY = r"\d+(?:[.,]\d+)?"
_UNIT = r"(?:\d+\s*)?[A-Za-z][A-Za-z.]*"

CURRENCY_PREFIX = re.compile(
    r"^(?:(?P<rp>rp\.?|idr)(?![a-z])|(?P<usd>us\$|usd)(?![a-z])|"
    r"(?P<sgd>s\$|sgd)(?![a-z])|(?P<myr>myr|rm(?=\d))|(?P<eur>eur|€)|"
    r"(?P<gbp>gbp|£)|(?P<usd2>\$))",
    re.IGNORECASE,
)
CURRENCY_CODES = {
    "rp": "IDR", "usd": "USD", "usd2": "USD", "sgd": "SGD",
    "myr": "MYR", "eur": "EUR", "gbp": "GBP",
}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "may": 5, "jun": 6,
    "jul": 7, "agu": 8, "ags": 8, "aug": 8, "sep": 9, "okt": 10, "oct": 10,
    "nov": 11, "des": 12, "dec": 12,
}
_MONTH_RX = "|".join(MONTHS)

DATE_NUMERIC = re.compile(r"(?<!\d)(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})(?!\d)")
DATE_TEXT = re.compile(
    rf"(?<!\d)(\d{{1,2}})\s+({_MONTH_RX})[a-z]*\.?,?\s+(\d{{2,4}})(?!\d)",
    re.IGNORECASE,
)
TIME_RX = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?!\d)")

# OCR sometimes fuses neighbouring columns: "125,20025,200" is "1  25,200  25,200".
GLUED_AMOUNTS = re.compile(r"(?:\d{1,3}(?:[.,]\d{3})+){2,}")
AMOUNT_PART = re.compile(r"\d{1,3}(?:[.,]\d{3})+")

NUMBERED_PREFIX = re.compile(r"^\s*\d{1,2}\s*[.)]\s+(?=\S)")

DETAIL_NO_NAME = re.compile(
    rf"^(?P<qty>{_QTY})\s*(?P<unit>{_UNIT})?\s*[x×*@]\s*(?P<price>{_MONEY})$",
    re.IGNORECASE,
)
DETAIL_NAMED = re.compile(
    rf"^(?P<name>.+?)\s+(?P<qty>{_QTY})\s*(?P<unit>{_UNIT})?\s*"
    rf"[x×*@]\s*(?P<price>{_MONEY})$",
    re.IGNORECASE,
)
COLUMNS = re.compile(
    rf"^(?:(?P<name>.+?)\s+)?(?P<qty>\d{{1,3}})\s+(?P<price>{_MONEY})$"
)
TRAILING_X_QTY = re.compile(r"^(?P<name>.+?)\s+[x×]\s*(?P<qty>\d{1,3})$", re.IGNORECASE)
LEADING_X_QTY = re.compile(r"^(?P<qty>\d{1,3})\s*[x×]\s*(?P<name>[^\W\d_].*)$", re.IGNORECASE)
LEADING_QTY = re.compile(r"^(?P<qty>\d{1,2})\s+(?P<name>[^\W\d_].*)$")

# Keyword groups.  Order of evaluation is defined in ``classify_label``.
RX = {
    "history": re.compile(
        r"history\s*pembayaran|riwayat\s*pembayaran|payment\s*history|"
        r"detail\s*pembayaran"
    ),
    "grand": re.compile(
        r"grand\s*total|total\s*(?:bayar|pembayaran|tagihan|belanja|akhir|due|"
        r"amount|payable|payment)|amount\s*(?:due|payable)|balance\s*due|"
        r"jumlah\s*(?:bayar|tagihan|akhir|total)|net\s*total|total\s*to\s*pay|"
        r"harus\s*dibayar|total\s*harga|nett?o\b"
    ),
    "item_count": re.compile(
        r"total\s*(?:qty|quantity|[il]te[mnr]s?|barang|produk|pcs)|"
        r"(?:qty|item|items)\s*total|jumlah\s*(?:item|barang|qty)|item\s*count"
    ),
    "subtotal": re.compile(r"sub\s*-?\s*total|subtotal|sub\s*jumlah"),
    "total": re.compile(r"^(?:total|jumlah|tagihan|amount)$"),
    "rounding": re.compile(r"pembulatan|rounding|round\s*off|rounded"),
    "discount": re.compile(
        r"\bdisc(?:ount)?\b|diskon|potongan|promo|voucher|hemat|coupon|kupon|"
        r"cashback|\bpot\.?\b"
    ),
    "service": re.compile(
        r"service|servis|\bsvc\b|\bs/?c\b|biaya\s*(?:layanan|admin|kirim|"
        r"pengiriman|pengemasan|lain)|layanan|\btips?\b|gratuity|ongkir|"
        r"delivery|packaging|admin\s*fee|platform\s*fee|handling"
    ),
    "tax": re.compile(r"\b(?:tax|ppn|pb\s*1|vat|gst|sst|pajak|pjk|pph)\b"),
    "payment": re.compile(
        r"tunai|cash|kembali|change|\bkartu\b|\bcard\b|debit|credit|kredit|"
        r"visa|master\s*card|mastercard|qris|gopay|go-pay|\bovo\b|\bdana\b|"
        r"shopee\s*pay|shopeepay|linkaja|e-?money|flazz|tapcash|brizzi|"
        r"\bpaid\b|payment|pembayaran|tendered|\bbayar\b|transfer|ewallet|"
        r"e-wallet|sisa\s*limit|saldo|diterima|received|\bbca\b|\bbni\b|"
        r"\bbri\b|mandiri|cimb"
    ),
    "meta": re.compile(
        r"kasir|cashier|\bnpwp\b|\bnib\b|telp|tlp|phone|\btel\b|\bfax\b|wifi|"
        r"wi-fi|terima\s*kasih|terimakasih|thank|kritik|saran|\bsms\b|\bwa\b|"
        r"whatsapp|www\.|\.com\b|\.co\.id|@|\btgl\b|tanggal|\bdate\b|"
        r"\bwaktu\b|invoice|struk|\bnota\b|\bbon\b|no\.?\s*(?:order|meja|"
        r"trx|transaksi|struk)|\bmeja\b|\btable\b|\border\b|\bmember\b|"
        r"\bpoin\b|\bpoints?\b|pelanggan|customer|\bguests?\b|\bpax\b|"
        r"\bserver\b|waiter|pelayan|\bstatus\b|\btipe\b|\btype\b|"
        r"jatuh\s*tempo|\bdue\b|\bjl\.?\b|jalan\b|\btbk\b|\bpt\.?\b|"
        r"\bdpp\b|\bnpwp\b|\bkode\b|\bkey\b|\bversi\b|\bv\.?\d|receipt|"
        r"\bbill\s*(?:no|#)|\bcheck\s*(?:no|#)|\bterminal\b|\bmid\b|\btid\b|"
        r"\bapproval\b|\bref(?:erence)?\b|\bbatch\b|\bnomor\b|\bno\.?\s*\d"
    ),
    "included": re.compile(r"\bincl|inclusive|included|termasuk|sudah\s*termasuk|\binc\b"),
}

# Words OCR often garbles; used for fuzzy matching of labels.
FUZZY_WORDS = [
    "total", "subtotal", "grand", "tunai", "kembalian", "kembali", "cash",
    "change", "discount", "diskon", "service", "tax", "pajak", "ppn",
    "bayar", "payment", "tendered", "amount", "balance", "item", "items",
]
_DIGIT_TO_LETTER = str.maketrans({"0": "o", "1": "l", "5": "s", "8": "b", "3": "e"})

GENERIC_HEADERS = re.compile(
    r"^(?:receipt|struk|nota|invoice|bill|welcome|selamat\s*datang|tax\s*invoice|"
    r"copy|customer\s*copy|duplicate|faktur)$",
    re.IGNORECASE,
)

SUMMARY_KINDS = {"subtotal", "total", "grand", "tax", "service", "discount", "rounding"}
REGION_END_KINDS = {"subtotal", "total", "grand", "payment", "history"}

ZERO = Decimal("0")


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class Cell:
    text: str
    confidence: float | None
    cx: float | None = None
    cy: float | None = None
    width: float | None = None
    height: float | None = None

    @property
    def x2(self) -> float | None:
        if self.cx is None or self.width is None:
            return None
        return self.cx + self.width / 2


@dataclass
class Token:
    text: str
    x2: float | None
    confidence: float | None
    money: Decimal | None = None
    negative: bool = False


@dataclass
class Row:
    cells: list[Cell]
    tokens: list[Token] = field(default_factory=list)
    currency: str | None = None

    @property
    def text(self) -> str:
        return " ".join(cell.text for cell in self.cells)

    @property
    def confidence(self) -> float | None:
        values = [c.confidence for c in self.cells if c.confidence is not None]
        return min(values) if values else None


# --------------------------------------------------------------------------
# Number handling
# --------------------------------------------------------------------------

def parse_amount(value: str) -> Decimal:
    """Parse a monetary string in Indonesian or international notation.

    "25.200" and "25,200" -> 25200;  "12.50" -> 12.5;  "1.234,56" -> 1234.56
    """
    value = re.sub(r"(?i)rp\.?|idr|[$€£]", "", value).strip().replace(" ", "")
    value = value.strip("()-−–")

    if not re.fullmatch(r"\d[\d.,]*", value):
        raise ValueError(f"Invalid monetary value: {value!r}")

    has_dot, has_comma = "." in value, "," in value

    if has_dot and has_comma:
        decimal_sep = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        value = value.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        parts = value.split(sep)
        if len(parts) > 2:
            value = "".join(parts)                      # 1.234.567
        elif len(parts[1]) == 3 and parts[0] != "0":
            value = "".join(parts)                      # 25.200
        else:
            value = ".".join(parts)                     # 12.50 / 0.375

    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Invalid monetary value: {value!r}") from error


def number(value: Decimal | None):
    """Decimal -> JSON-friendly int/float."""
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(round(value, 2))


def _is_price(body: str) -> bool:
    """A plausible price: has separators, decimals or at least 3 digits."""
    digits = re.sub(r"\D", "", body)
    if len(digits) > 10:
        return False
    return bool(re.search(r"[.,]", body)) or len(digits) >= 3


def _fix_digit_confusions(token: str) -> str:
    """Repair OCR letter/digit mix-ups inside numeric-looking tokens."""
    if not re.search(r"[.,]", token) or not re.search(r"\d", token):
        return token
    mapped = token.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "B": "8"}))
    return mapped if re.fullmatch(r"[\d.,]+", mapped) else token


# --------------------------------------------------------------------------
# Row building
# --------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def _estimate_skew(lines: list[dict]) -> float:
    """Median text-line angle (radians) from OCR polygons, if available."""
    angles = []
    for line in lines:
        poly = line.get("poly")
        if not poly or len(poly) < 2:
            continue
        (x0, y0), (x1, y1) = poly[0], poly[1]
        width = math.hypot(x1 - x0, y1 - y0)
        box = line.get("box")
        height = (box[3] - box[1]) if box else 0
        if width > 1.5 * max(height, 1):
            angles.append(math.atan2(y1 - y0, x1 - x0))
    if len(angles) < 3:
        return 0.0
    angle = statistics.median(angles)
    if abs(angle) < math.radians(0.4) or abs(angle) > math.radians(20):
        return 0.0
    return angle


def build_rows(lines: list[dict]) -> list[Row]:
    """Group OCR fragments into visual rows, left to right, top to bottom."""
    cells: list[Cell] = []
    has_geometry = True

    angle = _estimate_skew(lines)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    for line in lines:
        text = _normalize_text(str(line.get("text", "")))
        if not text:
            continue
        box = line.get("box")
        cell = Cell(text=text, confidence=line.get("confidence"))
        if box and len(box) == 4:
            x1, y1, x2, y2 = box
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            # Rotate by -angle so tilted text lines become horizontal.
            cell.cx = cx * cos_a + cy * sin_a
            cell.cy = -cx * sin_a + cy * cos_a
            cell.width = x2 - x1
            cell.height = max(y2 - y1, 1)
        else:
            has_geometry = False
        cells.append(cell)

    if not cells:
        return []

    if not has_geometry:
        return [Row(cells=[cell]) for cell in cells]

    median_height = statistics.median(cell.height for cell in cells)
    tolerance = 0.45 * median_height

    ordered = sorted(cells, key=lambda c: c.cy)
    rows: list[list[Cell]] = []
    centres: list[float] = []

    for cell in ordered:
        if rows and abs(cell.cy - centres[-1]) <= tolerance:
            rows[-1].append(cell)
            centres[-1] = statistics.fmean(c.cy for c in rows[-1])
        else:
            rows.append([cell])
            centres.append(cell.cy)

    return [Row(cells=sorted(group, key=lambda c: c.cx - c.width / 2)) for group in rows]


def tokenize_row(row: Row) -> None:
    """Split a row into tokens, flagging monetary values."""
    tokens: list[Token] = []
    currencies: list[str] = []

    for cell in row.cells:
        text = DATE_TEXT.sub(" ", cell.text)
        text = DATE_NUMERIC.sub(" ", text)
        text = TIME_RX.sub(" ", text)

        for raw in text.split():
            match = CURRENCY_PREFIX.match(raw)
            if match:
                code = CURRENCY_CODES.get(match.lastgroup)
                if code:
                    currencies.append(code)
                raw = raw[match.end():]
            raw = raw.strip("()[]{}*#|:;")
            if not raw:
                continue

            negative = False
            probe = raw
            if probe and probe[0] in "-−–" and len(probe) > 1:
                negative, probe = True, probe[1:]
            if probe and probe[-1] in "-−–" and len(probe) > 1:
                negative, probe = True, probe[:-1]

            probe = _fix_digit_confusions(probe.strip("()"))

            if not MONEY_TOKEN.match(probe) and GLUED_AMOUNTS.fullmatch(probe):
                for part in AMOUNT_PART.findall(probe):
                    tokens.append(Token(part, cell.x2, cell.confidence, parse_amount(part), False))
                continue

            money = None
            match = MONEY_TOKEN.match(probe)
            if match and _is_price(probe):
                try:
                    money = parse_amount(probe)
                except ValueError:
                    money = None

            tokens.append(Token(raw, cell.x2, cell.confidence, money, negative))

    row.tokens = tokens
    row.currency = currencies[0] if currencies else None


# --------------------------------------------------------------------------
# Label classification
# --------------------------------------------------------------------------

def _label_of(row: Row) -> str:
    words = [t.text for t in row.tokens if t.money is None]
    label = " ".join(words).lower()
    label = re.sub(r"[^a-z0-9/#.@\-\s]", " ", label)
    return re.sub(r"\s+", " ", label).strip()


def _fuzzy_label(label: str) -> str:
    """Repair common OCR damage in key words ('Tota1', 'Tuna1', 'Sub Totai')."""
    fixed = []
    for word in label.split():
        candidate = word
        if re.search(r"[a-z]", word) and re.search(r"\d", word):
            candidate = word.translate(_DIGIT_TO_LETTER)
        if candidate.isalpha() and len(candidate) >= 3 and candidate not in FUZZY_WORDS:
            close = difflib.get_close_matches(candidate, FUZZY_WORDS, n=1, cutoff=0.82)
            candidate = close[0] if close else word
        elif not candidate.isalpha():
            candidate = word
        fixed.append(candidate)
    return " ".join(fixed)


def classify_label(label: str, row: Row) -> str | None:
    """Return the row kind implied by its text, or None if it looks like an item."""
    label = _fuzzy_label(label)
    compact = re.sub(r"[^a-z ]", "", label).strip()

    if RX["history"].search(label):
        return "history"

    if RX["item_count"].search(label):
        # "Total Item   1   25.200" carries a subtotal; "Total Qty: 14" does not.
        numeric = [t for t in row.tokens if re.fullmatch(r"[\d.,]+", t.text)]
        if len(numeric) >= 2 and row.tokens and row.tokens[-1].money is not None:
            return "subtotal"
        return "meta"

    if RX["grand"].search(label):
        return "grand"
    if RX["subtotal"].search(label):
        return "subtotal"
    if RX["total"].match(compact):
        return "total"
    if re.match(r"^total\b", compact) and not RX["payment"].search(label):
        return "total"
    if RX["rounding"].search(label):
        return "rounding"
    if RX["discount"].search(label):
        return "discount"
    if RX["service"].search(label):
        return "service"
    if RX["tax"].search(label):
        return "tax"
    if RX["payment"].search(label):
        return "payment"
    if RX["meta"].search(label):
        return "meta"
    return None


# --------------------------------------------------------------------------
# Item interpretation
# --------------------------------------------------------------------------

@dataclass
class ItemParts:
    name: str
    quantity: Decimal
    unit: str
    unit_price: Decimal | None
    explicit: bool           # quantity/unit price came from an explicit pattern


def _to_decimal(text: str) -> Decimal:
    return parse_amount(text) if re.search(r"[.,]\d{3}\b", text) else Decimal(text.replace(",", "."))


def _normalise_unit(quantity: Decimal, unit: str | None) -> tuple[Decimal, str]:
    unit = (unit or "").strip().lower().rstrip(".")
    if unit in {"lusin", "lsn", "dozen", "doz"}:
        return quantity * 12, "pcs"
    if unit == "kodi":
        return quantity * 20, "pcs"
    return quantity, unit or "pcs"


def _clean_name(name: str) -> str:
    name = NUMBERED_PREFIX.sub("", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip(" .,:;-_*#|/\\~=@\"'")
    return name


def _letters(text: str) -> int:
    return len(re.findall(r"[^\W\d_]", text))


def interpret_description(description: str, total: Decimal | None) -> ItemParts:
    """Split a row description into name, quantity, unit and unit price."""
    description = _clean_name(description) if not description.strip() else description.strip()
    stripped = NUMBERED_PREFIX.sub("", description).strip()

    def build(match, named: bool) -> ItemParts:
        quantity = _to_decimal(match.group("qty"))
        quantity, unit = _normalise_unit(quantity, match.groupdict().get("unit"))
        name = _clean_name(match.group("name")) if named else ""
        return ItemParts(name, quantity, unit, parse_amount(match.group("price")), True)

    match = DETAIL_NO_NAME.match(stripped)
    if match:
        return build(match, named=False)

    match = DETAIL_NAMED.match(stripped)
    if match:
        return build(match, named=True)

    match = COLUMNS.match(stripped)
    if match:
        quantity = Decimal(match.group("qty"))
        unit_price = parse_amount(match.group("price"))
        name = _clean_name(match.group("name") or "")
        if quantity > 0:
            if total is None or abs(quantity * unit_price - total) <= max(Decimal("1"), total * Decimal("0.01")):
                return ItemParts(name, quantity, "pcs", unit_price, True)
        if total is not None and unit_price == total and name:
            return ItemParts(name, Decimal(1), "pcs", unit_price, True)

    # OCR sometimes glues the quantity to the unit price: "SUNLG MINT 755 125,200"
    # is really qty 1 x 25,200. Accept a split only when the arithmetic checks out.
    if total is not None:
        head, _, last = stripped.rpartition(" ")
        glued = re.fullmatch(r"(\d{1,2})(\d{1,3}(?:[.,]\d{3})+)", last)
        if head and glued:
            for qty_len in range(1, len(glued.group(1)) + 1):
                digits = last[:qty_len]
                rest = last[qty_len:]
                if not re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", rest):
                    continue
                quantity, unit_price = Decimal(digits), parse_amount(rest)
                if quantity > 0 and quantity * unit_price == total:
                    return ItemParts(_clean_name(head), quantity, "pcs", unit_price, True)

    match = TRAILING_X_QTY.match(stripped)
    if match:
        return ItemParts(_clean_name(match.group("name")), Decimal(match.group("qty")), "pcs", None, True)

    match = LEADING_X_QTY.match(stripped)
    if match:
        return ItemParts(_clean_name(match.group("name")), Decimal(match.group("qty")), "pcs", None, True)

    # A bare repeated price column: "NAME  35.000" + "35.000" total.
    match = re.match(rf"^(?P<name>.+?)\s+(?P<price>{_MONEY})$", stripped)
    if match and total is not None:
        try:
            price = parse_amount(match.group("price"))
        except ValueError:
            price = None
        if price is not None and price > 0 and total > price:
            ratio = total / price
            if ratio == ratio.to_integral_value() and 2 <= ratio <= 99:
                return ItemParts(_clean_name(match.group("name")), ratio, "pcs", price, True)
        if price is not None and price == total:
            return ItemParts(_clean_name(match.group("name")), Decimal(1), "pcs", price, True)

    # "2 Nasi Goreng 70.000": accept only when the total divides evenly.
    match = LEADING_QTY.match(stripped)
    if match and total is not None:
        quantity = Decimal(match.group("qty"))
        if 1 <= quantity <= 20 and total % quantity == 0:
            return ItemParts(_clean_name(match.group("name")), quantity, "pcs", None, False)

    return ItemParts(_clean_name(stripped), Decimal(1), "pcs", None, False)


# --------------------------------------------------------------------------
# Date / merchant / currency
# --------------------------------------------------------------------------

def _valid_date(year: int, month: int, day: int) -> date | None:
    if year < 100:
        year += 2000
    if not 2000 <= year <= 2100:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_date(rows: list[Row]) -> str | None:
    for row in rows:
        text = unicodedata.normalize("NFKC", row.text)
        if re.search(r"\bdue\b|jatuh\s*tempo|\bexp", text, re.IGNORECASE):
            continue

        for match in DATE_NUMERIC.finditer(text):
            a, b, c = (int(g) for g in match.groups())
            if len(match.group(1)) == 4:                  # yyyy-mm-dd
                found = _valid_date(a, b, c)
            else:                                           # dd-mm-yyyy (day first)
                day, month = a, b
                if month > 12 >= day:
                    day, month = month, day
                found = _valid_date(c, month, day)
            if found:
                return found.isoformat()

        match = DATE_TEXT.search(text)
        if match:
            found = _valid_date(
                int(match.group(3)), MONTHS[match.group(2).lower()[:3]], int(match.group(1))
            )
            if found:
                return found.isoformat()
    return None


def find_merchant(rows: list[Row]) -> str | None:
    for row in rows[:8]:
        text = row.text.strip()
        letters = _letters(text)
        if letters < 3 or letters < 0.5 * len(re.sub(r"\s", "", text)):
            continue
        if GENERIC_HEADERS.match(text):
            continue
        if RX["meta"].search(text.lower()) or any(t.money is not None for t in row.tokens):
            continue
        return text
    return None


def detect_currency(rows: list[Row]) -> str:
    found = [row.currency for row in rows if row.currency]
    if found:
        return max(set(found), key=found.count)

    # No symbol printed: decimals (12.50) imply a decimal currency, otherwise IDR.
    decimal_evidence = 0
    for row in rows:
        for token in row.tokens:
            if token.money is not None and re.search(r"[.,]\d{2}$", token.text):
                decimal_evidence += 1
    return "USD" if decimal_evidence >= 2 else "IDR"


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

def _merge_orphan_amounts(rows: list[Row]) -> list[Row]:
    """Attach an amount-only row to a preceding label row that lacks one.

    Handles OCR output without usable boxes, and rows split by skew.
    """
    merged: list[Row] = []
    for row in rows:
        previous = merged[-1] if merged else None
        amount_only = bool(row.tokens) and all(t.money is not None for t in row.tokens)
        if previous is not None and amount_only and previous.tokens:
            has_amount = any(t.money is not None for t in previous.tokens)
            label = _label_of(previous)
            kind = classify_label(label, previous) if label else None
            if not has_amount and kind in SUMMARY_KINDS | {"payment"}:
                previous.cells.extend(row.cells)
                previous.tokens.extend(row.tokens)
                continue
        merged.append(row)
    return merged


def _right_threshold(rows: list[Row]) -> float | None:
    lefts, rights = [], []
    for row in rows:
        for cell in row.cells:
            if cell.cx is None:
                return None
            lefts.append(cell.cx - cell.width / 2)
            rights.append(cell.cx + cell.width / 2)
    if len(lefts) < 4:
        return None
    lefts.sort()
    rights.sort()
    low = lefts[int(0.05 * (len(lefts) - 1))]
    high = rights[int(0.95 * (len(rights) - 1))]
    return low + 0.6 * (high - low)


def _last_money(row: Row) -> Token | None:
    for token in reversed(row.tokens):
        if token.money is not None:
            return token
    return None


def _split_row(row: Row, threshold: float | None, strict: bool):
    """Return (description, total_token) for a candidate item row."""
    tokens = list(row.tokens)

    # Drop trailing tax/status flags such as "T", "N", "*".
    while tokens and tokens[-1].money is None and len(tokens[-1].text) <= 2 and len(tokens) > 1:
        if re.search(r"\d", tokens[-1].text):
            break
        tokens.pop()

    if not tokens or tokens[-1].money is None:
        return " ".join(t.text for t in tokens), None

    # "2 x 35.000": the last number is a unit price, not the line total.
    if len(tokens) >= 2:
        before = tokens[-2].text.lower()
        if before in {"x", "×", "@", "*"} or re.fullmatch(r"\d+(?:[.,]\d+)?x", before):
            return " ".join(t.text for t in tokens), None

    total_token = tokens[-1]
    if strict and threshold is not None and total_token.x2 is not None:
        if total_token.x2 < threshold:
            return " ".join(t.text for t in tokens), None

    description = " ".join(t.text for t in tokens[:-1])
    return description, total_token


def parse_items(rows: list[Row], threshold: float | None, strict: bool):
    items: list[dict] = []
    pending: tuple[str, float | None] | None = None
    open_item: dict | None = None

    def add(parts: ItemParts, name: str, total: Decimal | None, confidence):
        nonlocal open_item
        quantity = parts.quantity if parts.quantity > 0 else Decimal(1)
        if total is None:
            if parts.unit_price is None:
                return
            total = parts.unit_price * quantity
        unit_price = parts.unit_price if parts.unit_price is not None else total / quantity
        item = {
            "name": name or "Item",
            "quantity": quantity,
            "unit": parts.unit,
            "unit_price": unit_price,
            "total_price": total,
            "confidence": confidence,
            "_open": False,
        }
        items.append(item)
        open_item = item
        return item

    for row in rows:
        description, total_token = _split_row(row, threshold, strict)
        total = total_token.money if total_token else None
        label = _label_of(row)
        confidence = row.confidence

        if total is not None and total_token.negative and total_token.money > 0:
            # Negative lines (vouchers etc.) are handled by the caller.
            open_item = None
            pending = None
            continue

        letters = _letters(description)
        meta_hit = bool(label) and classify_label(label, row) is not None

        parts = interpret_description(description, total) if description.strip() else None

        if total is not None:
            if parts is not None and parts.name and _letters(parts.name) >= (2 if strict else 1):
                if meta_hit:
                    pending, open_item = None, None
                    continue
                add(parts, parts.name, total, confidence)
                pending = None
                continue

            # Detail row (or a price on its own line): needs a pending name.
            if pending is not None:
                name, name_conf = pending
                detail = parts or ItemParts(name, Decimal(1), "pcs", None, False)
                if parts is not None and not parts.explicit and _letters(description) >= 2:
                    # Text without a recognisable quantity pattern is not a detail line.
                    pending = None
                    open_item = None
                    continue
                conf_values = [c for c in (name_conf, confidence) if c is not None]
                add(detail, name, total, min(conf_values) if conf_values else None)
                pending = None
                continue

            if open_item is not None and open_item["_open"] and parts is None:
                open_item["total_price"] = total
                open_item["unit_price"] = total / open_item["quantity"]
                open_item["_open"] = False
                continue
            continue

        # No total on this row.
        if parts is not None and parts.explicit and parts.unit_price is not None:
            if not parts.name:
                # "1 lusin x 36,000" with the line total on a following row.
                if pending is not None:
                    name, name_conf = pending
                    item = add(parts, name, None, name_conf)
                    if item:
                        item["_open"] = True
                    pending = None
                continue
            if _letters(parts.name) >= 2 and not meta_hit:
                # "Nasi Goreng 2 x 35.000" without a total column.
                item = add(parts, parts.name, None, confidence)
                if item:
                    item["_open"] = True
                pending = None
                continue

        if letters >= (2 if strict else 1) and not meta_hit:
            pending = (_clean_name(description), confidence)
            open_item = None
        else:
            if label and meta_hit:
                pending = None
            open_item = None

    for item in items:
        item.pop("_open", None)
    return items


def parse_receipt_text(ocr_result: dict) -> dict:
    lines = ocr_result.get("lines", []) or []

    all_rows = build_rows(lines)
    for row in all_rows:
        tokenize_row(row)
    rows = _merge_orphan_amounts([r for r in all_rows if r.tokens])

    receipt = {
        "merchant_name": find_merchant(all_rows),
        "transaction_date": find_date(all_rows),
        "currency": detect_currency(rows),
        "items": [],
        "subtotal": ZERO,
        "tax": ZERO,
        "tax_included": False,
        "service_charge": ZERO,
        "discount": ZERO,
        "rounding": ZERO,
        "total": ZERO,
        "warnings": [],
        "reconciliation": {},
    }

    # ---- classify rows -------------------------------------------------
    kinds: list[str | None] = []
    for row in rows:
        label = _label_of(row)
        kinds.append(classify_label(label, row) if label else None)

    end = next((i for i, k in enumerate(kinds) if k in REGION_END_KINDS), len(rows))
    first_payment = next((i for i, k in enumerate(kinds) if k == "payment"), len(rows))
    history_start = next((i for i, k in enumerate(kinds) if k == "history"), len(rows))

    # ---- items ---------------------------------------------------------
    threshold = _right_threshold(rows)
    region = rows[:end]
    items = parse_items(region, threshold, strict=True)
    if not items:
        items = parse_items(region, threshold, strict=False)

    # Drop item rows that are really summary lines (e.g. discount inside list).
    summary_in_region = {"discount": ZERO, "service": ZERO, "tax": ZERO, "rounding": ZERO}
    for i, row in enumerate(region):
        kind = kinds[i]
        if kind in summary_in_region:
            token = _last_money(row)
            if token is not None and not _is_percent_only(row, token):
                summary_in_region[kind] += token.money

    # ---- summary rows --------------------------------------------------
    totals: dict[str, list[Decimal]] = {k: [] for k in SUMMARY_KINDS}
    tax_after_payment = False
    included_hint = False
    tendered = change = None

    for i, row in enumerate(rows):
        if i >= history_start:
            break
        kind = kinds[i]
        token = _last_money(row)

        if kind == "payment":
            label = _label_of(row)
            if token is not None:
                if re.search(r"kembali|change", _fuzzy_label(label)):
                    change = token.money
                elif tendered is None and not re.search(r"limit|saldo|sisa", label):
                    tendered = token.money
            continue

        if kind not in SUMMARY_KINDS or token is None:
            if kind == "tax" and RX["included"].search(_label_of(row)):
                included_hint = True
            continue
        if kind in {"tax", "service", "discount"} and _is_percent_only(row, token):
            continue

        totals[kind].append(token.money)
        if kind == "tax":
            if i > first_payment:
                tax_after_payment = True
            if RX["included"].search(_label_of(row)):
                included_hint = True

    receipt["tax"] = sum(totals["tax"], ZERO)
    receipt["service_charge"] = sum(totals["service"], ZERO)
    receipt["discount"] = sum(totals["discount"], ZERO)
    receipt["rounding"] = sum(totals["rounding"], ZERO)

    printed_subtotal = totals["subtotal"][0] if totals["subtotal"] else None
    printed_total = None
    if totals["grand"]:
        printed_total = totals["grand"][-1]
    elif totals["total"]:
        printed_total = totals["total"][-1]
    elif tendered is not None and change is not None and tendered >= change:
        printed_total = tendered - change

    # ---- items to output ----------------------------------------------
    for item in items:
        low_confidence = item["confidence"] is not None and item["confidence"] < 0.85
        item["needs_review"] = bool(low_confidence)

    items_sum = sum((i["total_price"] for i in items), ZERO)
    subtotal = printed_subtotal if printed_subtotal is not None else items_sum

    # ---- tax inclusion & reconciliation ---------------------------------
    tax, service = receipt["tax"], receipt["service_charge"]
    discount, rounding = receipt["discount"], receipt["rounding"]
    tolerance = max(Decimal("1"), subtotal * Decimal("0.005"))

    exclusive = subtotal + tax + service - discount + rounding
    inclusive = subtotal + service - discount + rounding

    if tax == 0:
        tax_included = False
    elif included_hint or tax_after_payment:
        tax_included = True
    elif printed_total is not None:
        tax_included = abs(printed_total - inclusive) < abs(printed_total - exclusive)
    else:
        tax_included = False

    computed_total = inclusive if tax_included else exclusive
    total = printed_total if printed_total is not None else computed_total

    receipt["tax_included"] = tax_included
    receipt["subtotal"] = subtotal
    receipt["total"] = total

    warnings: list[str] = []
    if not items:
        warnings.append(
            "No line items could be read. Try a sharper, well-lit, flat photo "
            "or add the items by hand."
        )
    if printed_subtotal is not None and items and abs(printed_subtotal - items_sum) > tolerance:
        warnings.append(
            "Item prices add up to a different amount than the receipt's subtotal. "
            "An item may be missing or misread."
        )
    if printed_total is not None and abs(printed_total - computed_total) > tolerance and items:
        warnings.append(
            "Subtotal, tax, service and discount don't add up to the printed total."
        )
    if len(lines) < 4:
        warnings.append("Very little text was detected in the image.")
    if any(item["needs_review"] for item in items):
        warnings.append("Some items were read with low confidence and are highlighted.")

    if not items:
        status = "failed"
    elif printed_subtotal is not None and abs(printed_subtotal - items_sum) > tolerance:
        status = "mismatch"
    elif printed_total is not None and abs(printed_total - computed_total) > tolerance:
        status = "mismatch"
    elif printed_subtotal is not None or printed_total is not None:
        status = "ok"
    else:
        status = "unverified"

    receipt["warnings"] = warnings
    receipt["reconciliation"] = {
        "status": status,
        "items_sum": number(items_sum),
        "printed_subtotal": number(printed_subtotal),
        "printed_total": number(printed_total),
        "computed_total": number(computed_total),
    }

    # ---- serialise -----------------------------------------------------
    for key in ("subtotal", "tax", "service_charge", "discount", "rounding", "total"):
        receipt[key] = number(receipt[key])

    receipt["items"] = [
        {
            "name": item["name"],
            "quantity": number(item["quantity"]),
            "unit": item["unit"],
            "unit_price": number(item["unit_price"]),
            "total_price": number(item["total_price"]),
            "confidence": item["confidence"],
            "needs_review": item["needs_review"],
        }
        for item in items
    ]

    return receipt


def _is_percent_only(row: Row, token: Token) -> bool:
    """True for rows like 'PPN 11' where the number is a rate, not an amount."""
    if re.search(r"%", row.text) and token.money <= 100 and not re.search(r"[.,]", token.text):
        return True
    return bool(
        re.fullmatch(r"\d{1,2}", token.text) and token.money <= 25
    )
