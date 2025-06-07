from fastapi import APIRouter

from app.api.routes.invest import invest_router
from app.api.routes.news import news_router
from app.api.routes.pulse import pulse_router
from app.api.routes.llm import llm_router
from app.api.routes.auth import auth_router
from app.api.routes.tradingview import tradingview_router
from app.api.routes.parsers import parsers_router

main_router = APIRouter()

# СЮДА ПОДКЛЮЧАТЬ РОУТЕРЫ
main_router.include_router(pulse_router, prefix="/api/pulse", tags=["Pulse 💬"])
main_router.include_router(llm_router, prefix="/api/llm", tags=["LLM 🤖"])
main_router.include_router(auth_router, prefix="/api/auth", tags=["Auth 🔑"])
<<<<<<< HEAD
main_router.include_router(
    tradingview_router, prefix="/api/tradingview", tags=["TradingView 📈"]
)
main_router.include_router(
    parsers_router, prefix="/api/parsers", tags=["Parsers 🔍"]
)
=======
main_router.include_router(invest_router, prefix="/api/invest", tags=["Invest 💸"])
main_router.include_router(tradingview_router, prefix="/api/tradingview", tags=["Companies 🏢"])
main_router.include_router(news_router, prefix="/api/news", tags=["News 🗞️"])
>>>>>>> 44343264e618f5857f4ff0bbeffa24d7f63b739f
