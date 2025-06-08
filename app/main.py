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

origins = [
    "http://localhost:5173",  # Адрес для локальной разработки Svelte
    # Если у вас есть другие адреса, добавьте их сюда
]

# Добавление CORS middleware с правильными настройками
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # <<< ИЗМЕНЕНО: используем список доверенных доменов
    allow_credentials=True,  # <<< ВЕРНО: разрешаем cookie
    allow_methods=["*"],  # Разрешаем все методы
    allow_headers=["*"],  # Разрешаем все заголовки
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
