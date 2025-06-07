from fastapi import APIRouter
from app.api.routes.pulse import pulse_router
from app.api.routes.llm import llm_router
from app.api.routes.auth import auth_router

main_router = APIRouter()

# СЮДА ПОДКЛЮЧАТЬ РОУТЕРЫ
main_router.include_router(pulse_router, prefix="/api/pulse", tags=["Pulse 📰"])
main_router.include_router(llm_router, prefix="/api/llm", tags=["LLM 🤖"])
main_router.include_router(auth_router, prefix="/api/auth", tags=["Auth 🔑"])
