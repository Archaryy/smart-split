import threading
from pathlib import Path
from paddleocr import PaddleOCR

#initialize ocr only once
_ocr_engine = None
_engine_lock = threading.Lock()   # guards creation and prediction (engine is not thread-safe)

def get_ocr_engine():

    global _ocr_engine
    with _engine_lock:
        if _ocr_engine is None:
            # Initialize the PaddleOCR engine with English language support
            _ocr_engine = PaddleOCR(lang='en',
                                    use_doc_orientation_classify = False,
                                    use_doc_unwarping = False,
                                    use_textline_orientation = False,)
    return _ocr_engine

def extract_text(image_path: str | Path) -> dict:
    # Extract text from an image using PaddleOCR.

    # Args:
    #     image_path (str | Path): The path to the image file.
        
    # / 
    # Returns:
    #     dict: A dictionary containing the extracted text and additional information. 
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"The specified image file does not exist: {image_path}")
    
    ocr = get_ocr_engine()
    with _engine_lock:
        results = ocr.predict(str(image_path))

    if not results:
        return {"image" : image_path.name, 
                "line_count" : 0, 
                "lines" : [],
                "full_text" : ""}
        
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
        "line_count": len(lines),
        "lines": lines,
        "full_text": full_text
    }