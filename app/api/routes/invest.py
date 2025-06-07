from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from tinkoff.invest import (
    InstrumentIdType,
    InstrumentStatus,
    MoneyValue,
    OrderDirection,
    OrderType,
    Quotation,
    SecurityTradingStatus,
)
from tinkoff.invest.sandbox.client import SandboxClient
from enum import Enum
from datetime import date, datetime, timedelta

from app.api.deps import get_current_active_user
from app.models import User


async def get_current_user_with_invest_token(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Проверяет, что у пользователя есть инвестиционный токен.
    Возвращает пользователя, если токен есть.
    Иначе вызывает исключение 400 Bad Request.
    """
    if not current_user.invest_token:
        raise HTTPException(
            status_code=400,
            detail="Tinkoff API token is not configured for the user."
        )
    return current_user


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
    response_description="Результат пополнения счета",
)
async def top_up_sandbox_account(
    payload: SandboxTopUpRequest,
    account_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_with_invest_token),
):
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
    except HTTPException:
        # Пробрасываем HTTP-ошибки напрямую
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.get(
    "/sandbox/balance",
    summary="Получение баланса в песочнице",
    response_description="Баланс счета в песочнице",
)
async def get_sandbox_balance(
    account_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_with_invest_token),
):
    """
    Возвращает баланс указанного или первого доступного счета в песочнице.

    - **account_id**: (Опционально) ID счета для получения баланса.

    Доступно только для авторизованных пользователей.
    Для выполнения операции у пользователя должен быть задан токен Tinkoff API.
    """
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
    except HTTPException:
        # Пробрасываем HTTP-ошибки напрямую
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.post(
    "/sandbox/accounts",
    summary="Открыть новый счет в песочнице",
    response_description="ID нового счета в песочнице",
)
async def open_sandbox_account(
    current_user: User = Depends(get_current_user_with_invest_token),
):
    """
    Создает и открывает новый счет в песочнице Tinkoff.

    Доступно только для авторизованных пользователей.
    Для выполнения операции у пользователя должен быть задан токен Tinkoff API.
    """
    try:
        with SandboxClient(token=current_user.invest_token) as client:
            response = client.sandbox.open_sandbox_account()
            return {
                "message": "Sandbox account opened successfully.",
                "account_id": response.account_id
            }
    except HTTPException:
        # Пробрасываем HTTP-ошибки напрямую
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.get(
    "/sandbox/accounts",
    summary="Получить все счета в песочнице",
    response_description="Список счетов в песочнице",
)
async def get_sandbox_accounts(
    current_user: User = Depends(get_current_user_with_invest_token),
):
    """
    Возвращает список всех счетов пользователя в песочнице.

    Доступно только для авторизованных пользователей.
    """
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
    except HTTPException:
        # Пробрасываем HTTP-ошибки напрямую
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.delete(
    "/sandbox/accounts/{account_id}",
    summary="Закрыть счет в песочнице",
    response_description="Результат закрытия счета",
)
async def close_sandbox_account(
    account_id: str,
    current_user: User = Depends(get_current_user_with_invest_token),
):
    """
    Закрывает (удаляет) указанный счет в песочнице.

    - **account_id**: Идентификатор счета для закрытия.

    Доступно только для авторизованных пользователей.
    """
    try:
        with SandboxClient(token=current_user.invest_token) as client:
            client.sandbox.close_sandbox_account(account_id=account_id)
            return {
                "message": f"Sandbox account {account_id} closed successfully."
            }
    except HTTPException:
        # Пробрасываем HTTP-ошибки напрямую
        raise
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
    response_description="Результат размещения заявки",
)
async def post_sandbox_order(
    payload: SandboxOrderRequest,
    account_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_with_invest_token),
):
    """
    Размещает ордер на покупку или продажу в песочнице.

    - **ticker**: Тикер инструмента (например, `VKCO`).
    - **quantity**: Количество лотов.
    - **price**: (Опционально) Цена за 1 инструмент. Если не указана,
      исполняется рыночная заявка.
    - **direction**: Направление сделки (`buy` или `sell`).
    - **account_id**: (Опционально) ID счета. Если не указан, используется
      первый доступный.
    """
    try:
        with SandboxClient(token=current_user.invest_token) as client:
            target_account_id = account_id
            if not target_account_id:
                accounts = client.sandbox.get_sandbox_accounts().accounts
                if not accounts:
                    raise HTTPException(
                        status_code=404, detail="No sandbox accounts found.")
                target_account_id = accounts[0].id

            # Строгая проверка существования тикера
            all_shares = client.instruments.shares(
                instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE
            ).instruments

            # Проверяем, существует ли точно такой тикер
            exact_ticker_exists = any(
                share.ticker == payload.ticker for share in all_shares
            )

            if not exact_ticker_exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Instrument with ticker '{payload.ticker}' does not exist."
                )

            # Ищем инструмент по тикеру, чтобы получить FIGI
            find_instrument_response = client.instruments.find_instrument(
                query=payload.ticker)

            found_instruments = find_instrument_response.instruments
            if not found_instruments:
                raise HTTPException(
                    status_code=404, detail=f"Instrument with ticker '{payload.ticker}' not found."
                )

            # Получаем полную информацию по первому найденному инструменту
            figi = found_instruments[0].figi
            instrument_details_response = client.instruments.get_instrument_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                id=figi,
            )
            instrument = instrument_details_response.instrument

            # Проверяем, доступен ли инструмент для торгов
            is_tradable = (
                instrument.trading_status == SecurityTradingStatus.SECURITY_TRADING_STATUS_NORMAL_TRADING and
                instrument.buy_available_flag and
                instrument.sell_available_flag
            )
            if not is_tradable:
                raise HTTPException(
                    status_code=400,
                    detail=f"Instrument '{payload.ticker}' is found, but not available for trading now."
                )

            # Проверяем баланс перед покупкой
            if payload.direction == OrderDirectionEnum.BUY:
                positions = client.sandbox.get_sandbox_positions(
                    account_id=target_account_id)
                rub_balance = 0.0
                for money_val in positions.money:
                    if money_val.currency == 'rub':
                        rub_balance = _money_value_to_float(money_val)
                        break

                order_cost = 0.0
                if payload.price:  # Лимитная заявка
                    order_cost = payload.price * payload.quantity * instrument.lot
                else:  # Рыночная заявка, считаем примерную стоимость
                    last_prices = client.market_data.get_last_prices(figi=[
                                                                     figi])
                    if not last_prices.last_prices:
                        raise HTTPException(
                            status_code=400, detail=f"Could not get market price for {payload.ticker}.")

                    last_price_q = last_prices.last_prices[0].price
                    last_price_f = last_price_q.units + last_price_q.nano / 1e9
                    # Добавляем 5% запаса на волатильность
                    estimated_price = last_price_f * 1.05
                    order_cost = estimated_price * payload.quantity * instrument.lot

                if rub_balance < order_cost:
                    error_msg = f"Insufficient funds. Required: ~{order_cost:.2f} RUB, available: {rub_balance:.2f} RUB."
                    raise HTTPException(status_code=400, detail=error_msg)

            elif payload.direction == OrderDirectionEnum.SELL:
                positions = client.sandbox.get_sandbox_positions(
                    account_id=target_account_id)

                asset_position = None
                for security in positions.securities:
                    if security.figi == figi:
                        asset_position = security
                        break

                if not asset_position:
                    raise HTTPException(
                        status_code=400,
                        detail=f"You do not own any shares of '{payload.ticker}' to sell."
                    )

                required_shares_to_sell = payload.quantity * instrument.lot
                if asset_position.balance < required_shares_to_sell:
                    available_lots = asset_position.balance // instrument.lot
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Insufficient shares to sell for ticker '{payload.ticker}'. "
                            f"Requested to sell {payload.quantity} lot(s) ({required_shares_to_sell} shares), "
                            f"but you only have {available_lots} lot(s) ({asset_position.balance} shares)."
                        )
                    )

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
    except HTTPException:
        # Пробрасываем HTTP-ошибки напрямую
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


@invest_router.get(
    "/sandbox/tradable-shares",
    summary="Получить список доступных для торговли акций",
    response_description="Список акций, доступных для торговли в песочнице",
)
async def get_tradable_shares(
    current_user: User = Depends(get_current_user_with_invest_token),
):
    """
    Возвращает список акций, которыми можно торговать в данный момент
    в песочнице (статус NORMAL_TRADING, разрешена покупка/продажа).
    Возвращает не более 20 инструментов.
    """
    try:
        with SandboxClient(token=current_user.invest_token) as client:
            shares_response = client.instruments.shares(
                instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE
            )

            potentially_tradable = []
            for share in shares_response.instruments:
                if (share.trading_status == SecurityTradingStatus.SECURITY_TRADING_STATUS_NORMAL_TRADING and
                    share.buy_available_flag and
                    share.sell_available_flag and
                        share.currency == 'rub'):
                    potentially_tradable.append(share)
                # Увеличим лимит до 50 для предварительного отбора
                if len(potentially_tradable) >= 50:
                    break

            # Выполняем дополнительную проверку на наличие рыночной цены
            tradable_shares = []
            if potentially_tradable:
                # Собираем FIGI всех потенциально доступных инструментов
                figis = [share.figi for share in potentially_tradable]

                # Запрашиваем последние цены
                try:
                    last_prices_response = client.market_data.get_last_prices(
                        figi=figis)
                    last_prices = {
                        price.figi: price for price in last_prices_response.last_prices}

                    # Фильтруем только те, для которых есть рыночная цена
                    for share in potentially_tradable:
                        if share.figi in last_prices:
                            price = last_prices[share.figi].price
                            price_value = price.units + price.nano / 1_000_000_000

                            tradable_shares.append({
                                "ticker": share.ticker,
                                "figi": share.figi,
                                "name": share.name,
                                "lot": share.lot,
                                "price": price_value,
                                "currency": share.currency
                            })

                            if len(tradable_shares) >= 20:
                                break
                except Exception as price_error:
                    # Логируем ошибку, но продолжаем выполнение
                    pass

            return tradable_shares
    except HTTPException:
        # Пробрасываем HTTP-ошибки напрямую
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")


class OperationsFormatEnum(str, Enum):
    FULL = "full"
    TICKERS = "tickers"


@invest_router.get(
    "/sandbox/operations",
    summary="Получить историю операций по счету",
    response_description="История операций или список уникальных тикеров",
)
async def get_sandbox_operations(
    account_id: str | None = Query(
        default=None, description="ID счета для получения операций"),
    format: OperationsFormatEnum = Query(
        default=OperationsFormatEnum.FULL, description="Формат вывода: 'full' для полной истории, 'tickers' для списка тикеров"),
    from_date: date | None = Query(
        default=None, description="Начало периода в формате YYYY-MM-DD"),
    to_date: date | None = Query(
        default=None, description="Конец периода в формате YYYY-MM-DD"),
    current_user: User = Depends(get_current_user_with_invest_token),
):
    """
    Возвращает историю операций по счету.

    - **account_id**: (Опционально) ID счета. Если не указан, используется первый доступный.
    - **format**: (Опционально) Формат ответа: `full` (по умолчанию) или `tickers`.
    - **from_date**: (Опционально) Начало периода выборки. По умолчанию - 1 год назад.
    - **to_date**: (Опционально) Конец периода выборки. По умолчанию - сегодня.
    """
    try:
        with SandboxClient(token=current_user.invest_token) as client:
            target_account_id = account_id
            if not target_account_id:
                accounts = client.sandbox.get_sandbox_accounts().accounts
                if not accounts:
                    raise HTTPException(
                        status_code=404, detail="No sandbox accounts found.")
                target_account_id = accounts[0].id

            to_time = datetime.combine(
                to_date, datetime.max.time()) if to_date else datetime.utcnow()
            from_time = datetime.combine(from_date, datetime.min.time(
            )) if from_date else to_time - timedelta(days=365)

            operations_response = client.operations.get_operations(
                account_id=target_account_id,
                from_=from_time,
                to=to_time,
            )
            operations = operations_response.operations

            if not operations:
                return []

            figis = {op.figi for op in operations if op.figi}

            figi_to_ticker_map = {}
            if figis:
                all_shares = client.instruments.shares(
                    instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL
                ).instruments
                figi_to_ticker_map = {
                    share.figi: share.ticker for share in all_shares}

            if format == OperationsFormatEnum.TICKERS:
                tickers = {figi_to_ticker_map.get(
                    figi) for figi in figis if figi_to_ticker_map.get(figi)}
                return sorted(list(tickers))

            result = []
            for op in operations:
                result.append({
                    "id": op.id,
                    "date": op.date.isoformat(),
                    "type": op.type.name,
                    "ticker": figi_to_ticker_map.get(op.figi, op.figi),
                    "price": _money_value_to_float(op.price),
                    "payment": _money_value_to_float(op.payment),
                    "quantity": op.quantity,
                    "status": op.state.name,
                })

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Tinkoff API: {e}")
