from app.services.receipt_parser import parse_receipt_text

sample_ocr = {
    "lines": [
        {"text": "Smart CAFE", "confidence": 0.99},
        {"text": "Nasi Goreng 2 x 25.000", "confidence": 0.97},
        {"text": "Es Teh 8000", "confidence": 0.98},
        {"text": "Subtotal 58.000", "confidence": 0.96},
        {"text": "PPN 10%", "confidence": 0.99},
        {"text": "TOTAL 63.800", "confidence": 0.97},            
    ]
}

result = parse_receipt_text(sample_ocr)
print("\n ---PARSED RECEIPT---")

for key, value in result.items():
    print(f"{key}: {value}")