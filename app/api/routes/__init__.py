from fastapi import APIRouter
from app.api.routes.pulse import pulse_router

main_router = APIRouter()

# СЮДА ПОДКЛЮЧАТЬ РОУТЕРЫ
main_router.include_router(pulse_router)
