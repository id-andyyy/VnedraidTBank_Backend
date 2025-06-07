from fastapi import APIRouter
from app.api.routes.pulse import pulse_router
from app.api.routes.llm import llm_router

main_router = APIRouter()

# СЮДА ПОДКЛЮЧАТЬ РОУТЕРЫ
main_router.include_router(pulse_router)
main_router.include_router(llm_router)
