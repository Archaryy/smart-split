import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load the fast OCR model in the background so the first upload isn't slow.
    # (The slower, more accurate model loads only if a receipt needs it.)
    def warm_up():
        try:
            from app.services.ocr_service import get_ocr_engine
            get_ocr_engine("small")
        except Exception as error:  # the first real request will report it
            print(f"OCR warm-up failed: {error}")

    threading.Thread(target=warm_up, daemon=True).start()
    yield


app = FastAPI(
    title = "SmartSplit API",
    description = "AI-powered expense splitting and management tool",
    version = "0.1.0",
    lifespan = lifespan,
)

from app.api.routes.receipts import router as receipts_router
app.include_router(receipts_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the SmartSplit API!"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy",
            "application": "SmartSplit",}