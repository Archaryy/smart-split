from typing import Literal

from pydantic import BaseModel, Field


class ReceiptUploadResponse(BaseModel):
    message: str
    receipt_id: str
    filename: str
    original_filename: str
    format: Literal["JPEG", "PNG", "WEBP"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    size_bytes: int = Field(gt=0)
    status: Literal["pending_ocr"]


class ReceiptItem(BaseModel):
    name: str
    quantity: float = Field(default=1, ge=0)
    unit: str = "pcs"
    unit_price: float = 0
    total_price: float = 0
    confidence: float | None = None
    needs_review: bool = False


class Reconciliation(BaseModel):
    """How well the printed totals agree with the parsed items."""

    status: Literal["ok", "mismatch", "unverified", "failed"]
    items_sum: float = 0
    printed_subtotal: float | None = None
    printed_total: float | None = None
    computed_total: float = 0


class ReceiptData(BaseModel):
    merchant_name: str | None = None
    transaction_date: str | None = None  # ISO date
    currency: str = "IDR"

    items: list[ReceiptItem] = Field(default_factory=list)
    subtotal: float = 0
    tax: float = 0
    tax_included: bool = False
    service_charge: float = 0
    discount: float = 0
    rounding: float = 0
    total: float = 0

    warnings: list[str] = Field(default_factory=list)
    reconciliation: Reconciliation


class AnalyzeResponse(BaseModel):
    receipt_id: str
    status: Literal["analyzed"]
    ocr: dict
    receipt: ReceiptData
