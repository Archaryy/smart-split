import threading
from pathlib import Path

from paddleocr import PaddleOCR

from app.services.image_enhance import VARIANTS, load_image

# PP-OCRv6 "small" reads an ordinary receipt in a few seconds; "medium" is
# noticeably more accurate on hard photos but takes about a minute on a CPU.
MODELS = {
    "small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
    "medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
}

_engines: dict[str, PaddleOCR] = {}   # each model set is loaded once, on first use
_engine_lock = threading.Lock()       # guards creation and prediction (engines are not thread-safe)

def get_ocr_engine(model: str = "small"):
    if model not in MODELS:
        raise ValueError(f"Unknown OCR model: {model}")

    with _engine_lock:
        if model not in _engines:
            detection, recognition = MODELS[model]
            _engines[model] = PaddleOCR(lang='en',
                                        text_detection_model_name = detection,
                                        text_recognition_model_name = recognition,
                                        use_doc_orientation_classify = False,
                                        use_doc_unwarping = False,
                                        use_textline_orientation = False,)
    return _engines[model]

def extract_text(image_path: str | Path, variant: str = "original", model: str = "small") -> dict:
    """Run OCR on an image and return its text lines with positions.

    Args:
        image_path: path to the image file.
        variant: pre-processing applied first - "original" (default, resize only),
            "enhanced" (contrast boost + denoise for faint/tinted/unevenly lit
            photos).
        model: "small" (fast, default) or "medium" (slow, more accurate).

    Returns a dict with `lines` (text, confidence, box, poly), `full_text`, etc.
    """
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"The specified image file does not exist: {image_path}")

    if variant not in VARIANTS:
        raise ValueError(f"Unknown image variant: {variant}")

    image = VARIANTS[variant](load_image(image_path))

    ocr = get_ocr_engine(model)
    with _engine_lock:
        results = ocr.predict(image)

    if not results:
        return {"image": image_path.name,
                "variant": variant,
                "model": model,
                "line_count": 0,
                "lines": [],
                "full_text": ""}

    result = results[0]  # Get the first result (assuming single image input)

    texts = result.get("rec_texts", [])
    scores = result.get("rec_scores", [])
    boxes = result.get("rec_boxes", [])
    polys = result.get("rec_polys", [])

    if hasattr(boxes, "tolist"):
        boxes = boxes.tolist()  # Convert to list if it's a numpy array
    if hasattr(polys, "tolist"):
        polys = polys.tolist()

    lines = []

    for index, (text, score, box) in enumerate(zip(texts, scores, boxes)):
        line = {
            "text": str(text),
            "confidence": round(float(score), 4),
            "box": [int(value) for value in box]  # Ensure box coordinates are integers
        }
        # Rotated outline of the text line; lets the parser straighten tilted photos.
        if index < len(polys):
            poly = polys[index]
            if hasattr(poly, "tolist"):
                poly = poly.tolist()
            line["poly"] = [[round(float(x), 1), round(float(y), 1)] for x, y in poly]
        lines.append(line)

    full_text = "\n".join([line["text"] for line in lines])

    return {
        "image": image_path.name,
        "variant": variant,
        "model": model,
        "line_count": len(lines),
        "lines": lines,
        "full_text": full_text
    }
