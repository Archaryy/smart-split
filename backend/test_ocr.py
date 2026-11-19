from pathlib import Path
from app.services.ocr_service import extract_text

upload_dir = Path("uploads")

images = [
    path for path in upload_dir.iterdir() if path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
]

if not images:
    print("No images found in the 'uploads' directory.")
else:
    image_path = images[0]  # Get the first image
    print(f"Extracting text from: {image_path.name}")
    result = extract_text(image_path)
    print("\n---OCR Result---")
    print("Image:", result["image"])
    print("Detected Lines:", result["line_count"])

    print("\n---RECOGNIZED TEXT---")

    for line in result["lines"]:
        print(f"Text: {line['text']}, Confidence: {line['confidence']:.2f}")
        
    print("\n---FULL TEXT---")
    print(result["full_text"])