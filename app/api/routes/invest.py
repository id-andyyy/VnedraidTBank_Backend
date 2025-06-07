from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from tinkoff.invest import MoneyValue, OrderDirection, OrderType, Quotation
from tinkoff.invest.sandbox.client import SandboxClient
from enum import Enum

from app.api.deps import get_current_active_user
from app.models import User

invest_router = APIRouter()


class SandboxTopUpRequest(BaseModel):
    amount: float = Field(..., gt=0,
                          description="Сумма для пополнения в рублях")


def _money_value_to_float(money: MoneyValue) -> float:
    """Helper to convert MoneyValue to float."""
    if not money:
        return 0.0
    return money.units + money.nano / 1_000_000_000


def _float_to_quotation(value: float) -> Quotation:
    """Helper to convert float to Quotation."""
    units = int(value)
    nano = int((value - units) * 1_000_000_000)
    return Quotation(units=units, nano=nano)


@invest_router.post(
    "/sandbox/topup",
    summary="Пополнение баланса в песочнице",
    tags=["Tinkoff Invest"],
    response_description="Результат пополнения счета",
)
async def top_up_sandbox_account(
    payload: SandboxTopUpRequest,
    account_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
):
    if not current_user.invest_token:
        raise HTTPException(
            status_code=400,
            detail="Tinkoff API token is not configured for the user."
        )

    try:
        with SandboxClient(token=current_user.invest_token) as client:
            target_account_id = account_id
            if not target_account_id:
                accounts_response = client.sandbox.get_sandbox_accounts()
                accounts = accounts_response.accounts
                if not accounts:
                    raise HTTPException(
                        status_code=404, detail="No sandbox accounts found.")
                target_account_id = accounts[0].id

            units = int(payload.amount)
            nano = int((payload.amount - units) * 1_000_000_000)

            money_amount = MoneyValue(units=units, nano=nano, currency="rub")

            pay_in_response = client.sandbox.sandbox_pay_in(
                account_id=target_account_id,
                amount=money_amount
            )

            new_balance_float = _money_value_to_float(pay_in_response.balance)

            return {
                "message": "Sandbox account topped up successfully.",
                "account_id": target_account_id,
                "new_balance": new_balance_float,
                "currency": pay_in_response.balance.currency
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.get(
    "/sandbox/balance",
    summary="Получение баланса в песочнице",
    tags=["Tinkoff Invest"],
    response_description="Баланс счета в песочнице",
)
async def get_sandbox_balance(
    account_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
):
    """
    Возвращает баланс указанного или первого доступного счета в песочнице.

    - **account_id**: (Опционально) ID счета для получения баланса.

    Доступно только для авторизованных пользователей.
    Для выполнения операции у пользователя должен быть задан токен Tinkoff API.
    """
    if not current_user.invest_token:
        raise HTTPException(
            status_code=400,
            detail="Tinkoff API token is not configured for the user."
        )

    try:
        with SandboxClient(token=current_user.invest_token) as client:
            target_account_id = account_id
            if not target_account_id:
                accounts_response = client.sandbox.get_sandbox_accounts()
                accounts = accounts_response.accounts
                if not accounts:
                    raise HTTPException(
                        status_code=404, detail="No sandbox accounts found.")
                target_account_id = accounts[0].id

            portfolio = client.sandbox.get_sandbox_portfolio(
                account_id=target_account_id)

            total_currencies_value = portfolio.total_amount_currencies
            balance = _money_value_to_float(total_currencies_value)

            return {
                "account_id": target_account_id,
                "balance": balance,
                "currency": total_currencies_value.currency
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.post(
    "/sandbox/accounts",
    summary="Открыть новый счет в песочнице",
    tags=["Tinkoff Invest"],
    response_description="ID нового счета в песочнице",
)
async def open_sandbox_account(
    current_user: User = Depends(get_current_active_user),
):
    """
    Создает и открывает новый счет в песочнице Tinkoff.

    Доступно только для авторизованных пользователей.
    Для выполнения операции у пользователя должен быть задан токен Tinkoff API.
    """
    if not current_user.invest_token:
        raise HTTPException(
            status_code=400,
            detail="Tinkoff API token is not configured for the user."
        )

    try:
        with SandboxClient(token=current_user.invest_token) as client:
            response = client.sandbox.open_sandbox_account()
            return {
                "message": "Sandbox account opened successfully.",
                "account_id": response.account_id
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.get(
    "/sandbox/accounts",
    summary="Получить все счета в песочнице",
    tags=["Tinkoff Invest"],
    response_description="Список счетов в песочнице",
)
async def get_sandbox_accounts(
    current_user: User = Depends(get_current_active_user),
):
    """
    Возвращает список всех счетов пользователя в песочнице.

    Доступно только для авторизованных пользователей.
    """
    if not current_user.invest_token:
        raise HTTPException(
            status_code=400,
            detail="Tinkoff API token is not configured for the user."
        )

    try:
        with SandboxClient(token=current_user.invest_token) as client:
            response = client.sandbox.get_sandbox_accounts()
            accounts = response.accounts

            result = [
                {
                    "id": acc.id,
                    "type": acc.type.name,
                    "name": acc.name,
                    "status": acc.status.name,
                    "opened_date": acc.opened_date.isoformat(),
                }
                for acc in accounts
            ]
            return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.delete(
    "/sandbox/accounts/{account_id}",
    summary="Закрыть счет в песочнице",
    tags=["Tinkoff Invest"],
    response_description="Результат закрытия счета",
)
async def close_sandbox_account(
    account_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Закрывает (удаляет) указанный счет в песочнице.

    - **account_id**: Идентификатор счета для закрытия.

    Доступно только для авторизованных пользователей.
    """
    if not current_user.invest_token:
        raise HTTPException(
            status_code=400,
            detail="Tinkoff API token is not configured for the user."
        )

    try:
        with SandboxClient(token=current_user.invest_token) as client:
            client.sandbox.close_sandbox_account(account_id=account_id)
            return {
                "message": f"Sandbox account {account_id} closed successfully."
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


class OrderDirectionEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SandboxOrderRequest(BaseModel):
    ticker: str = Field(..., description="Тикер инструмента")
    quantity: int = Field(..., gt=0, description="Количество лотов для сделки")
    price: float | None = Field(
        default=None,
        description="Цена за единицу. Если не указана, используется рыночная цена."
    )
    direction: OrderDirectionEnum = Field(...,
                                          description="Направление сделки")


@invest_router.post(
    "/sandbox/orders",
    summary="Совершить сделку в песочнице",
    tags=["Tinkoff Invest"],
    response_description="Результат размещения заявки",
)
async def post_sandbox_order(
    payload: SandboxOrderRequest,
    account_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
):
    """
    Размещает ордер на покупку или продажу в песочнице.

    - **ticker**: Тикер инструмента (например, `GAZP`).
    - **quantity**: Количество лотов.
    - **price**: (Опционально) Цена за 1 инструмент. Если не указана,
      исполняется рыночная заявка.
    - **direction**: Направление сделки (`buy` или `sell`).
    - **account_id**: (Опционально) ID счета. Если не указан, используется
      первый доступный.
    """
    if not current_user.invest_token:
        raise HTTPException(
            status_code=400,
            detail="Tinkoff API token is not configured for the user."
        )

    try:
        with SandboxClient(token=current_user.invest_token) as client:
            target_account_id = account_id
            if not target_account_id:
                accounts = client.sandbox.get_sandbox_accounts().accounts
                if not accounts:
                    raise HTTPException(
                        status_code=404, detail="No sandbox accounts found.")
                target_account_id = accounts[0].id

            # Ищем инструмент по тикеру, чтобы получить FIGI
            instrument_response = client.instruments.find_instrument(
                query=payload.ticker)
            found_instruments = instrument_response.instruments
            if not found_instruments:
                raise HTTPException(
                    status_code=404, detail=f"Instrument with ticker '{payload.ticker}' not found.")

            # Для простоты берем первый найденный инструмент
            figi = found_instruments[0].figi

            order_direction = (
                OrderDirection.ORDER_DIRECTION_BUY
                if payload.direction == OrderDirectionEnum.BUY
                else OrderDirection.ORDER_DIRECTION_SELL
            )

            if payload.price:
                # Лимитная заявка
                order_type = OrderType.ORDER_TYPE_LIMIT
                price_quotation = _float_to_quotation(payload.price)
            else:
                # Рыночная заявка
                order_type = OrderType.ORDER_TYPE_MARKET
                price_quotation = None  # Цена для рыночной заявки не указывается

            order_response = client.sandbox.post_sandbox_order(
                figi=figi,
                quantity=payload.quantity,
                account_id=target_account_id,
                direction=order_direction,
                order_type=order_type,
                price=price_quotation,
            )

            return {
                "message": "Order placed successfully.",
                "order_id": order_response.order_id,
                "status": order_response.execution_report_status.name,
                "initial_price": _money_value_to_float(order_response.initial_order_price),
                "executed_lots": order_response.lots_executed,
                "total_order_amount": _money_value_to_float(order_response.total_order_amount),
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")
