import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

from sqlalchemy.exc import IntegrityError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import main_router

app = FastAPI(
    title="Mojarung Investments API",
    description="API for Mojarung Investments, providing access to financial data and analytics.",
    version="0.1.0"
)

# Добавление CORS middleware для разрешения всех источников
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=400,
        content={"message": f"Database integrity error: {exc.orig}"}
    )


app.include_router(main_router)


@app.get(
    "/api/health",
    description="Health check endpoint.",
    tags=["Health Check 👌"]
)
async def health_check():
    return {"status": "ok"}
