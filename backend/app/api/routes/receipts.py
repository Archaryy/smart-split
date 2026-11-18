from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image
import io

router = APIRouter(
    prefix="/api/receipts",
    tags=["receipts"]
)

ALLOWED_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp"
]

@router.post("/upload")
async def upload_receipt(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type.")
    contents = await file.read()
    
    if len(contents) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File size exceeds the 10 MB limit.")
    
    try:
        # Verify that the uploaded file is a valid image
        image = Image.open(io.BytesIO(contents))
        image.verify() 
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file")
    
    return {
        "message": "Receipt uploaded successfully.",
        "filename": file.filename, "format":image.format, "status": "pending_ocr"}