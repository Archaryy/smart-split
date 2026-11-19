from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.receipt import ReceiptUploadResponse
from PIL import Image
from pathlib import Path
import io
import uuid

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
    receipt_id = str(uuid.uuid4())
    extension = ALLOWED_FORMATS[image_format]
    saved_filename = f"{receipt_id}.{extension}"

    #save image
    file_path = UPLOAD_DIR / saved_filename
    file_path.write_bytes(contents)

    return {
        "message": "Receipt uploaded successfully.",
        "filename": saved_filename,
        "original_filename": file.filename,
        "format": image_format,
        "width": width,
        "height": height,
        "size_bytes": len(contents),
        "status": "pending_ocr"
    }