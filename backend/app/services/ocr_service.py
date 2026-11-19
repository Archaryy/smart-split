from pathlib import Path
from paddleocr import PaddleOCR

#initialize ocr only once
_ocr_engine = None

def get_ocr_engine():
    
    global _ocr_engine
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
    results = ocr.predict(str(image_path))  # Disable classification for faster processing

    if not results:
        return {"image" : image_path.name, 
                "line_count" : 0, 
                "lines" : [],
                "full_text" : ""}
        
    result = results[0]  # Get the first result (assuming single image input)
    
    texts = result.get("rec_texts", [])
    scores = result.get("rec_scores", [])
    boxes = result.get("rec_boxes", [])

    if hasattr(boxes, "tolist"):
        boxes = boxes.tolist()  # Convert to list if it's a numpy array
    
    lines = []

    for text, score, box in zip(texts, scores, boxes):
        lines.append({
            "text": str(text),
            "confidence": round(float(score), 4),
            "box": [int(value) for value in box]  # Ensure box coordinates are integers
        })
    
    full_text = "\n".join([line["text"] for line in lines])
    
    return {
        "image": image_path.name,
        "line_count": len(lines),
        "lines": lines,
        "full_text": full_text
    }