from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title = "SmartSplit API",
    description = "AI=powered expense splitting and management tool",
    version = "0.1.0",
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