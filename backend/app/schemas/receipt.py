from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from typing import Literal

class ReceiptUploadResponse(BaseModel):
    message: str
    receipt_id: str
    filenamae: str
    original_filename: str
    format: Literal["JPEG", "PNG", "WEBP"]
    width: int= Field(gt = 0)
    height: int= Field(gt = 0)
    size_bytes: int= Field(gt = 0)
    status: Literal["pending_ocr"]
    
class ReceiptItem(BaseModel):
    name: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    unit_price: Decimal = Field(default = Decimal("1"),gt=0)
    total_price: Decimal = Field(ge=0)
    
class ReceiptData(BaseModel):
    merchant_name: str | None = None
    transaction_date: date | None = None

    currency: str = "IDR"

    items: list[ReceiptItem] = Field(default_factory=list)
    subtotal: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    service_charge: Decimal = Field(default=Decimal("0"), ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(default=Decimal("0"), ge=0)
    
