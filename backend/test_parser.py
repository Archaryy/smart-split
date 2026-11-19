
from app.services.receipt_parser import parse_receipt_text

sample_ocr = {
    "lines": [
        {"text": "u Shop", "confidence": 0.9419},
        {"text": "Jl. Dr. Ir. H. Soekafio No.19,Me", "confidence": 0.9241},
        {"text": "2023-08-02", "confidence": 1.0},
        {"text": "1. Indomie Goreng", "confidence": 0.9756},
        {"text": "1 lusin x 36,000", "confidence": 0.9772},
        {"text": "Rp 36.000", "confidence": 0.9596},
        {"text": "2. Fruit Tea Apple", "confidence": 0.9972},
        {"text": "1 500 ml × 7,000", "confidence": 0.9717},
        {"text": "Rp 7.000", "confidence": 0.9995},
        {"text": "3. Belfood Sosis Bakar", "confidence": 1.0},
        {"text": "1 × 27,000", "confidence": 0.9531},
        {"text": "Rp 27.000", "confidence": 0.9682},
        {"text": "Total QTY:14", "confidence": 0.9996},
        {"text": "Sub Total", "confidence": 1.0},
        {"text": "Rp 70.000", "confidence": 0.9493},
        {"text": "Total", "confidence": 1.0},
        {"text": "Rp 70.000", "confidence": 0.9998},
        {"text": "Tipe: kredit", "confidence": 0.9879},
        {"text": "Sisa limit: Rp 10.000", "confidence": 0.9999},
        {"text": "History Pembayaran Utang:", "confidence": 1.0},
        {"text": "02/08/2023 Cash", "confidence": 0.9999},
        {"text": "Rp 60.000", "confidence": 0.9999}
    ]
}

result = parse_receipt_text(sample_ocr)

for item in result["items"]:
    print(item)

print("\nReceipt summary:")
for key, value in result.items():
    if key != "items":
        print(f"{key}: {value}")

# Basic validation
assert len(result["items"]) == 3
assert result["items"][0]["quantity"] == 12
assert result["items"][0]["total_price"] == 36000
assert result["items"][1]["unit"] == "500 ml"
assert result["items"][2]["total_price"] == 27000
assert result["subtotal"] == 70000
assert result["total"] == 70000

print("\nAll parser tests passed!")
