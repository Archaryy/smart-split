from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.receipt import AnalyzeResponse, ReceiptUploadResponse
from PIL import Image
from pathlib import Path
import io
import logging
from uuid import UUID, uuid4
from app.services.ocr_service import extract_text
from app.services.receipt_pipeline import read_receipt

logger = logging.getLogger("smartsplit.receipts")

router = APIRouter(
    prefix="/api/receipts",
    tags=["receipts"]
)

# storage location : backend/uploads
UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit

ALLOWED_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp"
}

@router.post("/upload", response_model=ReceiptUploadResponse)
async def upload_receipt(file: UploadFile = File(...)):
    # read uploaded file
    contents = await file.read()

    #validate file size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds the 10 MB limit.")
    
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    
    #verify actual image contents
    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()  # Verify that it's a valid image
        #reopen after verify to read image information
        image = Image.open(io.BytesIO(contents))
        
        image_format = image.format
        width, height = image.size

    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file.")
    
    #validate image format
    if image_format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported image format: {image_format}. Allowed formats: {list(ALLOWED_FORMATS.keys())}")
    
    #generate unique filename
    receipt_id = str(uuid4())
    extension = ALLOWED_FORMATS[image_format]
    saved_filename = f"{receipt_id}.{extension}"

    #save image
    file_path = UPLOAD_DIR / saved_filename
    file_path.write_bytes(contents)

    return {
    "message": "Receipt uploaded successfully.",
    "receipt_id": receipt_id,
    "filename": saved_filename,
    "original_filename": file.filename,
    "format": image_format,
    "width": width,
    "height": height,
    "size_bytes": len(contents),
    "status": "pending_ocr"
}


@router.post("/{receipt_id}/analyze", response_model=AnalyzeResponse)
def analyze_receipt(receipt_id: str):
    # Plain `def`: FastAPI runs it in a worker thread, so the slow, CPU-bound
    # OCR call does not block the event loop (health checks, other uploads).

    # 1. Validate receipt ID
    try:
        receipt_id = str(UUID(receipt_id))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid receipt ID"
        )

    # 2. Find uploaded image
    file_path = None

    for extension in ["jpg", "png", "webp"]:
        candidate = UPLOAD_DIR / f"{receipt_id}.{extension}"

        if candidate.exists():
            file_path = candidate
            break

    if file_path is None:
        raise HTTPException(
            status_code=404,
            detail="Receipt image not found"
        )

    # 3. Run OCR and parse, retrying with other image treatments if the first
    #    read doesn't look trustworthy (faint, tinted or unevenly lit photos).
    try:
        ocr_result, parsed_receipt = read_receipt(file_path, extract_text)

    except Exception:
        logger.exception("Receipt analysis failed for %s", receipt_id)

        raise HTTPException(
            status_code=500,
            detail="We couldn't read this receipt. Try a sharper, well-lit photo."
        )

    # 5. Return combined results
    return {
        "receipt_id": receipt_id,
        "status": "analyzed",
        "ocr": ocr_result,
        "receipt": parsed_receipt
    }
